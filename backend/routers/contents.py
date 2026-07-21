import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.audit.logger import log_action
from backend.auth.dependencies import require_permission
from backend.db import get_db
from backend.models import Article, ArticleAnalysis, Campaign, CampaignArticle, Source, User
from backend.models.articles import VALID_REVIEW_STATUSES

router = APIRouter(prefix="/api/contents", tags=["contents"])


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} không hợp lệ")


def _latest_analysis_ids_subquery(db: Session):
    """Subquery (article_id, max_analyzed_at) — dùng để xác định đúng bản ghi
    article_analysis MỚI NHẤT/bài. Cần thiết vì 1 bài có thể bị AI phân tích lại
    nhiều lần với kết quả khác nhau (rule 07 — qwen3:8b không cố định output giữa
    các lần gọi) — nếu không lọc theo bản mới nhất, list và detail có thể hiển thị
    sentiment khác nhau cho cùng 1 bài."""
    return (
        db.query(ArticleAnalysis.article_id, func.max(ArticleAnalysis.analyzed_at).label("max_at"))
        .group_by(ArticleAnalysis.article_id)
        .subquery()
    )


def _latest_analysis_map(db: Session, article_ids: list) -> dict:
    if not article_ids:
        return {}
    latest = _latest_analysis_ids_subquery(db)
    rows = (
        db.query(ArticleAnalysis)
        .join(
            latest,
            (ArticleAnalysis.article_id == latest.c.article_id)
            & (ArticleAnalysis.analyzed_at == latest.c.max_at),
        )
        .filter(ArticleAnalysis.article_id.in_(article_ids))
        .all()
    )
    return {row.article_id: row for row in rows}


def _get_latest_analysis(db: Session, article_id) -> ArticleAnalysis | None:
    return (
        db.query(ArticleAnalysis)
        .filter(ArticleAnalysis.article_id == article_id)
        .order_by(ArticleAnalysis.analyzed_at.desc())
        .first()
    )


def _campaign_ids_map(db: Session, article_ids: list) -> dict:
    if not article_ids:
        return {}
    rows = db.query(CampaignArticle).filter(CampaignArticle.article_id.in_(article_ids)).all()
    result: dict = {}
    for row in rows:
        result.setdefault(row.article_id, []).append(str(row.campaign_id))
    return result


def _serialize_analysis(analysis: "ArticleAnalysis | None") -> dict | None:
    if analysis is None:
        return None
    return {
        "analysis_id": str(analysis.analysis_id),
        "topics": analysis.topics,
        "keywords": analysis.keywords,
        "sentiment": analysis.sentiment,
        "emotion": analysis.emotion,
        "confidence": analysis.confidence,
        "needs_review": analysis.needs_review,
        "summary": analysis.summary,
        "ai_model": analysis.ai_model,
        "analyzed_at": analysis.analyzed_at,
    }


def _serialize_content_list_item(article: Article, analysis, source_name, campaign_ids: list) -> dict:
    return {
        "article_id": str(article.article_id),
        "url": article.url,
        "title": article.title,
        "author": article.author,
        "published_at": article.published_at,
        "crawled_at": article.crawled_at,
        "status": article.status,
        "review_status": article.review_status,
        "source_id": str(article.source_id) if article.source_id else None,
        "source_name": source_name,
        "campaign_ids": campaign_ids,
        "sentiment": analysis.sentiment if analysis else None,
        "emotion": analysis.emotion if analysis else None,
        "needs_review": analysis.needs_review if analysis else None,
    }


def _serialize_content_detail(article: Article, analysis, source_name, campaigns: list) -> dict:
    base = _serialize_content_list_item(
        article, analysis, source_name, [str(c.campaign_id) for c in campaigns]
    )
    base.update(
        {
            "content_raw": article.content_raw,
            "reviewed_by": str(article.reviewed_by) if article.reviewed_by else None,
            "reviewed_at": article.reviewed_at,
            "reviewer_note": article.reviewer_note,
            "campaigns": [{"campaign_id": str(c.campaign_id), "name": c.name} for c in campaigns],
            "analysis": _serialize_analysis(analysis),
        }
    )
    return base


def _get_article_or_404(db: Session, content_id: str) -> Article:
    try:
        article_uuid = uuid.UUID(content_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Không tìm thấy nội dung")
    article = db.get(Article, article_uuid)
    if article is None or article.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nội dung")
    return article


def _detail_related(db: Session, article: Article):
    analysis = _get_latest_analysis(db, article.article_id)
    source_name = None
    if article.source_id:
        source = db.get(Source, article.source_id)
        source_name = source.name if source else None
    campaign_ids = [
        row.campaign_id for row in db.query(CampaignArticle).filter_by(article_id=article.article_id).all()
    ]
    campaigns = db.query(Campaign).filter(Campaign.campaign_id.in_(campaign_ids)).all() if campaign_ids else []
    return analysis, source_name, campaigns


@router.get("")
def list_contents(
    campaign_id: str | None = None,
    source_id: str | None = None,
    sentiment: str | None = None,
    review_status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("content", "view")),
):
    query = db.query(Article).filter(Article.deleted_at.is_(None))

    if campaign_id:
        campaign_uuid = _parse_uuid(campaign_id, "campaign_id")
        article_ids_subq = (
            db.query(CampaignArticle.article_id)
            .filter(CampaignArticle.campaign_id == campaign_uuid)
            .scalar_subquery()
        )
        query = query.filter(Article.article_id.in_(article_ids_subq))

    if source_id:
        source_uuid = _parse_uuid(source_id, "source_id")
        query = query.filter(Article.source_id == source_uuid)

    if sentiment:
        # Không join trực tiếp ArticleAnalysis vào query chính (tránh nhân bản dòng
        # khi 1 bài có nhiều bản ghi analysis, và tránh lỗi Postgres khi kết hợp
        # DISTINCT với ORDER BY sau join) — lọc qua subquery article_id đã xác định
        # đúng bản MỚI NHẤT.
        latest = _latest_analysis_ids_subquery(db)
        sentiment_article_ids = (
            db.query(ArticleAnalysis.article_id)
            .join(
                latest,
                (ArticleAnalysis.article_id == latest.c.article_id)
                & (ArticleAnalysis.analyzed_at == latest.c.max_at),
            )
            .filter(ArticleAnalysis.sentiment == sentiment)
            .scalar_subquery()
        )
        query = query.filter(Article.article_id.in_(sentiment_article_ids))

    if review_status:
        query = query.filter(Article.review_status == review_status)

    if date_from:
        query = query.filter(Article.published_at >= date_from)
    if date_to:
        query = query.filter(Article.published_at <= date_to)

    articles = query.order_by(Article.crawled_at.desc()).all()

    article_ids = [a.article_id for a in articles]
    analysis_map = _latest_analysis_map(db, article_ids)
    campaign_ids_map = _campaign_ids_map(db, article_ids)
    source_ids = {a.source_id for a in articles if a.source_id}
    sources_map = (
        {s.source_id: s.name for s in db.query(Source).filter(Source.source_id.in_(source_ids)).all()}
        if source_ids
        else {}
    )

    return {
        "contents": [
            _serialize_content_list_item(
                a,
                analysis_map.get(a.article_id),
                sources_map.get(a.source_id),
                campaign_ids_map.get(a.article_id, []),
            )
            for a in articles
        ]
    }


@router.get("/{content_id}")
def get_content(
    content_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("content", "view")),
):
    article = _get_article_or_404(db, content_id)
    analysis, source_name, campaigns = _detail_related(db, article)
    return _serialize_content_detail(article, analysis, source_name, campaigns)


class ContentReviewRequest(BaseModel):
    review_status: str
    note: str | None = None


@router.post("/{content_id}/review")
def review_content(
    content_id: str,
    payload: ContentReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("content", "review")),
):
    # BR-CONTENT-03 đã enforce qua permission content.review (chỉ ADMIN/MANAGER/ANALYST
    # có permission này theo seed migration 0011) — không cần check role riêng ở đây.
    article = _get_article_or_404(db, content_id)

    if payload.review_status not in VALID_REVIEW_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"review_status phải là 1 trong {VALID_REVIEW_STATUSES}"
        )

    old_value = {"review_status": article.review_status, "reviewer_note": article.reviewer_note}

    article.review_status = payload.review_status
    article.reviewed_by = current_user.user_id
    article.reviewed_at = func.now()
    if payload.note is not None:
        article.reviewer_note = payload.note

    db.flush()

    log_action(
        db,
        user_id=current_user.user_id,
        action="content.review",
        entity_type="article",
        entity_id=article.article_id,
        old_value=old_value,
        new_value={"review_status": article.review_status, "reviewer_note": article.reviewer_note},
        request=request,
    )
    db.commit()

    analysis, source_name, campaigns = _detail_related(db, article)
    return _serialize_content_detail(article, analysis, source_name, campaigns)
