# Chia đều số bài crawl theo nguồn — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm công tắc `.env` `EVEN_DISTRIBUTE_ACROSS_SOURCES` — khi bật, `_crawl_sources()` chia đều `MAX_ARTICLES_PER_JOB` cho từng nguồn đã chọn (thay vì nguồn đầu tiên ăn hết ngân sách), để test với ít bài vẫn thấy đa dạng nguồn thật.

**Architecture:** Thêm 1 hàm thuần `_distribute_evenly(total, n) -> list[int]` (không phụ thuộc DB, dễ test độc lập) tính quota cố định cho từng nguồn theo đúng thứ tự `job.source_ids`, dư dồn cho nguồn đầu. `_crawl_sources()` dùng quota này làm điều kiện dừng bổ sung **cho từng nguồn**, song song với điều kiện dừng tổng job đã có sẵn. Khi cờ tắt (mặc định), hành vi giữ nguyên y hệt hiện tại.

**Tech Stack:** Python, SQLAlchemy, pytest, Postgres (test qua `docker compose exec backend pytest`).

**Spec liên quan:** `docs/superpowers/specs/2026-07-10-even-distribute-sources-design.md` (đã duyệt với user — đọc trước khi implement, có đầy đủ lý do các quyết định: dư dồn nguồn đầu, không bù thiếu hụt, mặc định tắt).

---

## File Structure

- Modify: `backend/workers/report_job.py` — thêm `_distribute_evenly()`, sửa `_crawl_sources()`
- Test: `backend/tests/test_report_job.py` — test cho `_distribute_evenly()` + test tích hợp crawl
- Modify: `.env.example` — thêm biến mới
- Modify: `.claude/rules/06-crawler-strategy.md` — thêm quy tắc mới
- Modify: `CLAUDE.md` — ghi nhận hoàn thành + kết quả verify thật (task cuối)

---

## Task 1: Hàm phân bổ thuần `_distribute_evenly()`

**Files:**
- Modify: `backend/workers/report_job.py`
- Test: `backend/tests/test_report_job.py`

- [ ] **Step 1: Viết test thất bại**

Thêm vào `backend/tests/test_report_job.py` (thêm `_distribute_evenly` vào import ở dòng `from backend.workers.report_job import _analyze_articles, _crawl_sources`):

```python
from backend.workers.report_job import _analyze_articles, _crawl_sources, _distribute_evenly


def test_distribute_evenly_splits_remainder_to_first_sources():
    assert _distribute_evenly(5, 3) == [2, 2, 1]


def test_distribute_evenly_splits_exactly_when_divisible():
    assert _distribute_evenly(6, 3) == [2, 2, 2]


def test_distribute_evenly_allows_zero_quota_when_fewer_articles_than_sources():
    assert _distribute_evenly(2, 5) == [1, 1, 0, 0, 0]


def test_distribute_evenly_single_source_gets_everything():
    assert _distribute_evenly(7, 1) == [7]
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `docker compose exec backend pytest backend/tests/test_report_job.py -k distribute_evenly -v`
Expected: FAIL — `ImportError: cannot import name '_distribute_evenly'`

- [ ] **Step 3: Implement**

Trong `backend/workers/report_job.py`, thêm hàm mới ngay sau `_parse_max_articles()` (trước `_get_candidates()`):

```python
def _distribute_evenly(total: int, n: int) -> list[int]:
    # Chia total thành n phần gần bằng nhau nhất, số dư dồn cho các phần tử ĐẦU tiên theo
    # thứ tự — khớp thứ tự source_ids user đã chọn ở FE. VD total=5, n=3 → [2, 2, 1].
    base, remainder = divmod(total, n)
    return [base + 1 if i < remainder else base for i in range(n)]
```

- [ ] **Step 4: Chạy lại test để xác nhận pass**

Run: `docker compose exec backend pytest backend/tests/test_report_job.py -k distribute_evenly -v`
Expected: 4/4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/workers/report_job.py backend/tests/test_report_job.py
git commit -m "feat: thêm _distribute_evenly() — chia đều số bài cho nhiều nguồn, dư dồn nguồn đầu"
```

---

## Task 2: Tích hợp quota vào `_crawl_sources()`

**Files:**
- Modify: `backend/workers/report_job.py`
- Test: `backend/tests/test_report_job.py`

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `backend/tests/test_report_job.py`:

```python
def test_crawl_sources_distributes_evenly_across_sources_when_flag_enabled(db_session, monkeypatch):
    monkeypatch.setenv("MAX_ARTICLES_PER_JOB", "5")
    monkeypatch.setenv("EVEN_DISTRIBUTE_ACROSS_SOURCES", "true")

    source_a = Source(name="A", domain=f"a-{uuid.uuid4()}.example", group_name="A", parsing_rules={})
    source_b = Source(name="B", domain=f"b-{uuid.uuid4()}.example", group_name="B", parsing_rules={})
    source_c = Source(name="C", domain=f"c-{uuid.uuid4()}.example", group_name="C", parsing_rules={})
    db_session.add_all([source_a, source_b, source_c])
    db_session.flush()

    job = Job(
        source_ids=[source_a.source_id, source_b.source_id, source_c.source_id],
        date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
    )
    db_session.add(job)
    db_session.flush()

    # Mỗi nguồn có dư candidate (4 mỗi nguồn) để đảm bảo quota là yếu tố giới hạn, không
    # phải do thiếu candidate.
    def fake_get_article_urls(source, date_from, date_to):
        return (
            [{"url": f"https://{source.domain}/a-{i}", "lastmod": date(2026, 6, 1)} for i in range(4)],
            [],
        )

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url, "url_hash": f"hash-{url}", "title": "Title", "content_raw": "Content",
            "author": None, "published_at": None, "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", side_effect=fake_get_article_urls), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        count_a = db_session.query(Article).filter_by(job_id=job.job_id, source_id=source_a.source_id).count()
        count_b = db_session.query(Article).filter_by(job_id=job.job_id, source_id=source_b.source_id).count()
        count_c = db_session.query(Article).filter_by(job_id=job.job_id, source_id=source_c.source_id).count()
        assert (count_a, count_b, count_c) == (2, 2, 1)
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source_a)
        db_session.delete(source_b)
        db_session.delete(source_c)
        db_session.commit()


def test_crawl_sources_does_not_compensate_shortfall_from_other_sources(db_session, monkeypatch):
    monkeypatch.setenv("MAX_ARTICLES_PER_JOB", "5")
    monkeypatch.setenv("EVEN_DISTRIBUTE_ACROSS_SOURCES", "true")

    source_a = Source(name="A", domain=f"a-{uuid.uuid4()}.example", group_name="A", parsing_rules={})
    source_b = Source(name="B", domain=f"b-{uuid.uuid4()}.example", group_name="B", parsing_rules={})
    source_c = Source(name="C", domain=f"c-{uuid.uuid4()}.example", group_name="C", parsing_rules={})
    db_session.add_all([source_a, source_b, source_c])
    db_session.flush()

    job = Job(
        source_ids=[source_a.source_id, source_b.source_id, source_c.source_id],
        date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
    )
    db_session.add(job)
    db_session.flush()

    # Quota tính được là [2, 2, 1] cho A/B/C. Nguồn A chỉ có 1 candidate (thiếu 1 so với quota).
    def fake_get_article_urls(source, date_from, date_to):
        if source.source_id == source_a.source_id:
            return ([{"url": f"https://{source.domain}/only-one", "lastmod": date(2026, 6, 1)}], [])
        return (
            [{"url": f"https://{source.domain}/a-{i}", "lastmod": date(2026, 6, 1)} for i in range(4)],
            [],
        )

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url, "url_hash": f"hash-{url}", "title": "Title", "content_raw": "Content",
            "author": None, "published_at": None, "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", side_effect=fake_get_article_urls), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        count_a = db_session.query(Article).filter_by(job_id=job.job_id, source_id=source_a.source_id).count()
        count_b = db_session.query(Article).filter_by(job_id=job.job_id, source_id=source_b.source_id).count()
        count_c = db_session.query(Article).filter_by(job_id=job.job_id, source_id=source_c.source_id).count()
        total = db_session.query(Article).filter_by(job_id=job.job_id).count()

        assert count_a == 1  # thiếu hụt, không bù
        assert count_b == 2  # vẫn đúng quota của B, không nhận thêm phần thiếu của A
        assert count_c == 1
        assert total == 4  # ít hơn MAX_ARTICLES_PER_JOB=5 — đánh đổi đã chốt trong spec
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source_a)
        db_session.delete(source_b)
        db_session.delete(source_c)
        db_session.commit()


def test_crawl_sources_does_not_distribute_when_flag_disabled(db_session, monkeypatch):
    monkeypatch.setenv("MAX_ARTICLES_PER_JOB", "5")
    monkeypatch.delenv("EVEN_DISTRIBUTE_ACROSS_SOURCES", raising=False)

    source_a = Source(name="A", domain=f"a-{uuid.uuid4()}.example", group_name="A", parsing_rules={})
    source_b = Source(name="B", domain=f"b-{uuid.uuid4()}.example", group_name="B", parsing_rules={})
    db_session.add_all([source_a, source_b])
    db_session.flush()

    job = Job(
        source_ids=[source_a.source_id, source_b.source_id],
        date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
    )
    db_session.add(job)
    db_session.flush()

    def fake_get_article_urls(source, date_from, date_to):
        return (
            [{"url": f"https://{source.domain}/a-{i}", "lastmod": date(2026, 6, 1)} for i in range(10)],
            [],
        )

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url, "url_hash": f"hash-{url}", "title": "Title", "content_raw": "Content",
            "author": None, "published_at": None, "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", side_effect=fake_get_article_urls), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        count_a = db_session.query(Article).filter_by(job_id=job.job_id, source_id=source_a.source_id).count()
        count_b = db_session.query(Article).filter_by(job_id=job.job_id, source_id=source_b.source_id).count()

        # Hành vi cũ (cờ tắt/mặc định): nguồn A (đầu tiên) ăn hết ngân sách, nguồn B không có bài nào
        assert count_a == 5
        assert count_b == 0
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source_a)
        db_session.delete(source_b)
        db_session.commit()
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `docker compose exec backend pytest backend/tests/test_report_job.py -k "distributes_evenly or does_not_compensate or does_not_distribute_when_flag_disabled" -v`
Expected: `test_crawl_sources_distributes_evenly_across_sources_when_flag_enabled` và `test_crawl_sources_does_not_compensate_shortfall_from_other_sources` FAIL (chưa có logic quota, tất cả bài sẽ dồn hết vào nguồn A); `test_crawl_sources_does_not_distribute_when_flag_disabled` PASS ngay từ đầu (đây là test hành vi cũ, dùng để xác nhận baseline không bị phá — vẫn giữ lại trong bộ test)

- [ ] **Step 3: Implement**

Sửa `backend/workers/report_job.py`, thay toàn bộ hàm `_crawl_sources()`:

```python
def _crawl_sources(db, job: Job) -> None:
    delay_seconds = float(os.environ.get("CRAWLER_DELAY_SECONDS", "1.5"))
    max_articles = _parse_max_articles(os.environ.get("MAX_ARTICLES_PER_JOB"))
    even_distribute = os.environ.get("EVEN_DISTRIBUTE_ACROSS_SOURCES", "false").lower() == "true"
    # Chia đều max_articles cho từng nguồn đã chọn (đúng thứ tự job.source_ids) — chỉ áp
    # dụng khi bật cờ VÀ có giới hạn tổng (max_articles=None nghĩa là không giới hạn, chia
    # đều một giá trị vô hạn không có ý nghĩa). None = giữ nguyên hành vi cũ, chỉ check tổng job.
    per_source_quota: list[int] | None = None
    if even_distribute and max_articles is not None and job.source_ids:
        per_source_quota = _distribute_evenly(max_articles, len(job.source_ids))

    # Chỉ chống trùng URL TRONG PHẠM VI 1 lần chạy job này (không đụng DB) — một số nguồn
    # (VD sitemap index) có thể vô tình trả về cùng 1 URL 2 lần. KHÔNG chặn URL đã crawl ở
    # job khác: mỗi job crawl/phân tích độc lập, kể cả trùng URL với job trước (xem spec
    # docs/superpowers/specs/2026-07-09-remove-cross-job-dedup-design.md). UNIQUE composite
    # (job_id, url_hash) ở DB (migration 0009) là lưới an toàn dự phòng cho trường hợp check
    # này có bug bỏ sót — không phải cơ chế chính, không cần xử lý IntegrityError riêng ở đây.
    seen_urls: set[str] = set()

    def crawled_count() -> int:
        return db.query(Article).filter_by(job_id=job.job_id).count()

    def source_crawled_count(source_id) -> int:
        return db.query(Article).filter_by(job_id=job.job_id, source_id=source_id).count()

    for idx, source_id in enumerate(job.source_ids):
        if max_articles is not None and crawled_count() >= max_articles:
            break

        source = db.get(Source, source_id)
        try:
            candidates, failed_locs = _get_candidates(source, job.date_from, job.date_to)
        except Exception:
            logger.exception("Lỗi lấy danh sách bài viết cho nguồn %s", source.domain)
            continue

        for loc in failed_locs:
            db.add(
                Article(
                    job_id=job.job_id,
                    source_id=source.source_id,
                    url=loc,
                    url_hash=compute_url_hash(loc),
                    status="error",
                )
            )
            db.commit()

        for candidate in candidates:
            if max_articles is not None and crawled_count() >= max_articles:
                break
            if per_source_quota is not None and source_crawled_count(source.source_id) >= per_source_quota[idx]:
                break

            if candidate["url"] in seen_urls:
                continue
            seen_urls.add(candidate["url"])
            url_hash = compute_url_hash(candidate["url"])

            try:
                parsed = fetch_article_dispatch(candidate["url"], source.parsing_rules)
            except Exception:
                logger.exception("Crawl lỗi (exception), đánh dấu error: %s", candidate["url"])
                parsed = None
            time.sleep(delay_seconds)
            if parsed is None:
                logger.warning("Crawl lỗi (hết retry hoặc không parse được), đánh dấu error: %s", candidate["url"])
                db.add(
                    Article(
                        job_id=job.job_id,
                        source_id=source.source_id,
                        url=candidate["url"],
                        url_hash=url_hash,
                        status="error",
                    )
                )
                db.commit()
                continue

            # Một số nguồn (VD bocongan.gov.vn) không có published_at từ chính trang bài viết
            # (thiếu meta article:published_time) — dùng lại ngày đã lấy từ trang danh sách
            # (candidate["lastmod"], đã lọc date_from/date_to ở bước lấy candidate) làm dự
            # phòng, ưu tiên published_at thật nếu có.
            candidate_lastmod = candidate.get("lastmod")
            published_at = parsed.get("published_at") or (
                datetime.combine(candidate_lastmod, datetime.min.time()) if candidate_lastmod else None
            )
            if published_at and not (job.date_from <= published_at.date() <= job.date_to):
                # Sitemap phẳng/listing-page không lọc được chính xác theo ngày trước khi fetch
                # (VD bocongan.gov.vn ghi <lastmod> giống nhau cho mọi URL, không phải ngày đăng
                # thật) — lọc lại ở đây bằng ngày đăng thật lấy từ chính bài viết. Không phải
                # lỗi nên không insert status=error, chỉ bỏ qua âm thầm.
                logger.info("Bỏ qua bài ngoài khoảng ngày yêu cầu (%s): %s", published_at.date(), candidate["url"])
                continue

            db.add(
                Article(
                    job_id=job.job_id,
                    source_id=source.source_id,
                    url=parsed["url"],
                    url_hash=parsed["url_hash"],
                    title=parsed["title"],
                    content_raw=parsed["content_raw"],
                    author=parsed["author"],
                    published_at=published_at,
                    crawl_duration_seconds=parsed.get("crawl_duration_seconds"),
                )
            )
            db.commit()
```

(Thay đổi so với bản gốc: thêm tính `even_distribute`/`per_source_quota` ở đầu hàm, đổi `for source_id in job.source_ids:` → `for idx, source_id in enumerate(job.source_ids):`, thêm hàm `source_crawled_count()`, thêm 1 điều kiện `break` mới trong vòng lặp candidate. Toàn bộ phần còn lại giữ nguyên y hệt.)

- [ ] **Step 4: Chạy lại toàn bộ test report_job**

Run: `docker compose exec backend pytest backend/tests/test_report_job.py -v`
Expected: toàn bộ PASS (test cũ + 4 test `_distribute_evenly` + 3 test tích hợp mới)

- [ ] **Step 5: Chạy toàn bộ test suite backend**

Run: `docker compose exec backend pytest backend/tests/ -v`
Expected: toàn bộ PASS (baseline trước task này: 113 test — xem không bị phá vỡ)

- [ ] **Step 6: Commit**

```bash
git add backend/workers/report_job.py backend/tests/test_report_job.py
git commit -m "feat: chia đều MAX_ARTICLES_PER_JOB cho từng nguồn khi bật EVEN_DISTRIBUTE_ACROSS_SOURCES"
```

---

## Task 3: Cập nhật `.env.example` và rule doc

**Files:**
- Modify: `.env.example`
- Modify: `.claude/rules/06-crawler-strategy.md`

- [ ] **Step 1: Thêm biến vào `.env.example`**

Tìm dòng cuối cùng của file:
```
MAX_ARTICLES_PER_JOB=
```

Thay bằng:
```
MAX_ARTICLES_PER_JOB=
# true = chia đều MAX_ARTICLES_PER_JOB cho từng nguồn đã chọn (dư dồn nguồn đầu theo thứ
# tự source_ids), false/để trống = giữ hành vi cũ (nguồn đầu tiên ăn hết ngân sách trước)
EVEN_DISTRIBUTE_ACROSS_SOURCES=false
```

- [ ] **Step 2: Thêm quy tắc vào `06-crawler-strategy.md`**

Tìm đoạn `**Quy tắc:**` (danh sách bullet ngay dưới phần code block `fetch_article_dispatch`), thêm 1 bullet mới ngay sau bullet đầu tiên (bullet dedup):

```markdown
- `MAX_ARTICLES_PER_JOB` mặc định áp dụng tuần tự theo `source_ids` — nguồn đầu tiên đủ bài sẽ "ăn hết" ngân sách trước khi chạm tới nguồn sau. Bật `EVEN_DISTRIBUTE_ACROSS_SOURCES=true` để chia đều ngân sách cho từng nguồn đã chọn (dư dồn nguồn đầu theo thứ tự `source_ids`) — hữu ích khi test với số bài nhỏ nhưng muốn thấy đa dạng nguồn. Không bù thiếu hụt: nguồn nào không đủ bài để lấp đầy quota của nó thì lấy được bấy nhiêu, tổng job có thể ít hơn `MAX_ARTICLES_PER_JOB` đã cấu hình (xem lý do đầy đủ ở `docs/superpowers/specs/2026-07-10-even-distribute-sources-design.md`)
```

- [ ] **Step 3: Verify**

Run: `grep -n "EVEN_DISTRIBUTE_ACROSS_SOURCES" .env.example .claude/rules/06-crawler-strategy.md`
Expected: xuất hiện ở cả 2 file

- [ ] **Step 4: Commit**

```bash
git add .env.example .claude/rules/06-crawler-strategy.md
git commit -m "docs: thêm EVEN_DISTRIBUTE_ACROSS_SOURCES vào .env.example và 06-crawler-strategy.md"
```

---

## Task 4: Verify thật với dữ liệu thật

**Không có file code ở task này — chạy job thật qua API để xác nhận tính năng giải quyết đúng vấn đề user báo cáo (1 nguồn ăn hết ngân sách).**

- [ ] **Step 1: Đảm bảo service đang chạy** (worktree docker stack đã tắt sau Slice 4 — cần bật lại)

```bash
docker compose up -d postgres redis backend celery-worker
docker compose restart celery-worker   # bắt buộc sau khi đổi code .py — xem CLAUDE.md
```

Nếu cần remap port do trùng với stack `main` đang chạy song song, dùng lại `docker-compose.override.yml` đã tạo ở lần verify Slice 4 (port 5433/6380/8001, `OLLAMA_BASE_URL=http://host.docker.internal:11434` trỏ về Ollama của stack `main` đã có sẵn model — xem lịch sử phiên làm việc trước, không cần pull lại model).

- [ ] **Step 2: Set biến môi trường cho container** (thêm vào `.env` của worktree — file này không commit, chỉ dùng local)

```
MAX_ARTICLES_PER_JOB=5
EVEN_DISTRIBUTE_ACROSS_SOURCES=true
```

Restart lại backend + celery-worker sau khi đổi `.env`:
```bash
docker compose up -d backend celery-worker
```

- [ ] **Step 3: Lấy 3 source_id thật (VD VTV, VOV, vietnam.vn) qua API**

```bash
curl -s http://localhost:8001/api/sources | python3 -m json.tool
```

- [ ] **Step 4: Tạo job thật với 3 nguồn, khoảng ngày đủ rộng để mỗi nguồn có bài**

```bash
curl -s -X POST http://localhost:8001/api/reports/create \
  -H "Content-Type: application/json" \
  -d '{"source_ids": ["<VTV_ID>", "<VOV_ID>", "<VIETNAMVN_ID>"], "date_from": "2026-06-01", "date_to": "2026-07-08"}'
```

- [ ] **Step 5: Polling tới `completed`, rồi query DB đối chiếu số bài từng nguồn**

```bash
docker compose exec -T postgres psql -U ngs -d ngs_monitor -c "
SELECT s.name, COUNT(*)
FROM articles a JOIN sources s ON s.source_id = a.source_id
WHERE a.job_id = '<job_id>'
GROUP BY s.name;
"
```

Expected: cả 3 nguồn đều xuất hiện với số bài gần 2/2/1 (đúng `_distribute_evenly(5, 3)`), KHÔNG còn tình trạng chỉ 1 nguồn có bài như trước khi có tính năng này.

- [ ] **Step 6: Ghi lại kết quả thật** (job_id, số bài từng nguồn) để đưa vào Task 5

---

## Task 5: Cập nhật CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Thêm bullet vào "Đã hoàn thành"** (dùng đúng số liệu thật từ Task 4, không phải số ví dụ)

Thêm bullet mới vào cuối danh sách `### Đã hoàn thành`, theo mẫu:

```markdown
- **Chia đều số bài crawl theo nguồn (2026-07-10):** thêm công tắc `EVEN_DISTRIBUTE_ACROSS_SOURCES` (mặc định tắt, giữ hành vi cũ) — khi bật, `_crawl_sources()` chia đều `MAX_ARTICLES_PER_JOB` cho từng nguồn đã chọn theo đúng thứ tự `source_ids` (dư dồn nguồn đầu, không bù thiếu hụt giữa các nguồn — xem spec `docs/superpowers/specs/2026-07-10-even-distribute-sources-design.md`). Giải quyết vấn đề đã ghi nhận nhiều lần ở Slice 2/3/4 verify: nguồn đầu tiên luôn "ăn hết" ngân sách, không test được đa dạng nguồn với số bài nhỏ. **Đã verify job thật** (job `<job_id thật>`, 3 nguồn VTV/VOV/vietnam.vn, `MAX_ARTICLES_PER_JOB=5`): kết quả `<số liệu thật, VD VTV=2, VOV=2, vietnam.vn=1>`, đúng phân bổ `_distribute_evenly(5, 3) = [2, 2, 1]`.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: cập nhật CLAUDE.md — chia đều số bài theo nguồn, ghi nhận verify thật"
```

---

## Self-Review Checklist

- **Spec coverage:** spec yêu cầu (1) công tắc `.env` mặc định tắt → Task 3; (2) chia đều dư dồn nguồn đầu → Task 1; (3) không bù thiếu hụt → Task 2 (test `does_not_compensate`); (4) verify thật → Task 4. Đủ.
- **Placeholder scan:** không còn "TBD"/số liệu giả — Task 4/5 yêu cầu điền số liệu thật, không phải ví dụ.
- **Type consistency:** `_distribute_evenly(total: int, n: int) -> list[int]` dùng nhất quán ở Task 1 (định nghĩa) và Task 2 (gọi trong `_crawl_sources`); `per_source_quota` cùng kiểu `list[int] | None` xuyên suốt.
