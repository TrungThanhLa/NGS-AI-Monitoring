"""cập nhật parsing_rules bocongan.gov.vn sang listing_pages thật, xoá sitemap_url đã đóng băng

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-07
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

OLD_PARSING_RULES = json.dumps({"engine": "crawl4ai"})
OLD_SITEMAP_URL = "https://bocongan.gov.vn/sitemap.xml"

NEW_PARSING_RULES = json.dumps(
    {
        "engine": "crawl4ai",
        "listing_item": "article.card-large",
        "listing_link": 'a[href^="/bai-viet/"]',
        "listing_date": "span.text-bca-gray-700",
        "listing_pages": [
            "https://bocongan.gov.vn/chuyen-muc/chi-dao-dieu-hanh",
            "https://bocongan.gov.vn/chuyen-muc/hoat-dong-cua-bo-cong-an-1754966863",
            "https://bocongan.gov.vn/chuyen-muc/hoat-dong-cua-dia-phuong-1753170286",
            "https://bocongan.gov.vn/chuyen-muc/hoat-dong-xa-hoi-1753170294",
            "https://bocongan.gov.vn/chuyen-muc/nguoi-tot-viec-tot-1753170210",
            "https://bocongan.gov.vn/chuyen-muc/thong-tin-doi-ngoai-1751367399",
            "https://bocongan.gov.vn/chuyen-muc/tin-an-ninh-trat-tu-1753170263",
        ],
    }
)


def upgrade():
    op.execute(
        sa.text(
            """
            UPDATE sources
            SET parsing_rules = CAST(:parsing_rules AS jsonb), sitemap_url = NULL
            WHERE domain = 'bocongan.gov.vn'
            """
        ).bindparams(parsing_rules=NEW_PARSING_RULES)
    )


def downgrade():
    op.execute(
        sa.text(
            """
            UPDATE sources
            SET parsing_rules = CAST(:parsing_rules AS jsonb), sitemap_url = :sitemap_url
            WHERE domain = 'bocongan.gov.vn'
            """
        ).bindparams(parsing_rules=OLD_PARSING_RULES, sitemap_url=OLD_SITEMAP_URL)
    )
