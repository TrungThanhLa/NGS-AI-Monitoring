# BoCongAn Giai đoạn B — Listing-Page Selector thật Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuyển bocongan.gov.vn từ sitemap đã đóng băng (xem CLAUDE.md, xác nhận 2026-07-07) sang crawl 7 trang "chuyên mục" thật bằng CSS selector đã verify trực tiếp trên site — hoàn tất Giai đoạn A (`parsing_rules.listing_pages`/`fetch_pages`, đã code nhưng chưa có selector thật + chưa migrate DB).

**Architecture:**
- `listing_item`/`listing_link`/`listing_date` là CSS selector thật lấy từ HTML thật của bocongan.gov.vn (curl trực tiếp 7/7 trang chuyên mục, xác nhận đồng nhất 100%)
- **Sửa sai lầm ở bản nháp đầu (đã bị người dùng chỉ ra đúng, verify lại bằng chính HTML thật):** mỗi trang chuyên mục có 2 vùng khác nhau — cột chính (`lg:col-span-8`, có `<h3 class="category-title">{tên chuyên mục}</h3>`) chứa đúng 10 bài MỚI NHẤT của CHÍNH chuyên mục đang xem, dạng `article.card-large`; cột phụ bên phải (`lg:col-span-4`) là 2 widget CHUNG toàn site ("Tin tức mới cập nhật", "Tin đọc nhiều trong tuần"), không liên quan chuyên mục đang xem, chứa `card-medium`/`card-small`. Bản nháp đầu lấy nhầm `card-small` (38 item, trùng hợp khớp số ước tính cũ trong CLAUDE.md) — **sai**, phải lấy `card-large` (10 item, đúng nội dung chuyên mục)
- href trả về là đường dẫn tương đối (`/bai-viet/...`) — cần `urljoin`, đúng như CLAUDE.md đã dự đoán trước ("nguồn listing-page khác sau này nếu trả href tương đối thì cần xử lý qua urljoin"). Không cần sửa gì khác ở `listing.py` — `card-large` có `<a>` lồng BÊN TRONG `<article>` nên code hiện tại (`item.select_one(rules["listing_link"])`) đã hoạt động đúng, không cần hack "item tự là link" như bản nháp đầu
- **Phát hiện thứ hai (từ câu hỏi của người dùng):** trang bài viết thật của bocongan.gov.vn không có meta tag `article:published_time` mà `crawl4ai_client.py` dùng để lấy `published_at` → cột này sẽ vẫn `NULL` dù đã chuyển sang listing_pages, **trừ khi** dùng lại ngày đã lấy được từ chính trang danh sách (`candidate["lastmod"]`, đã verify là ngày thật, hiển thị ngay trên trang chuyên mục) làm dự phòng. Đây là giải pháp đơn giản hơn nhiều so với việc dạy `crawl4ai_client.py` đọc JSON-LD — tái dùng dữ liệu đã có sẵn, không thêm cơ chế parse mới
- Không cần sửa `crawl4ai_client.py` — title/content vẫn lấy qua `engine=crawl4ai` như cũ (đã verify hoạt động ở Slice 2)
- **Không làm phân trang / không dùng form lọc theo ngày của site trong lần này (quyết định của người dùng):** cả nút phân trang ("of 193 pages") lẫn form lọc "Từ ngày"/"Đến ngày" (`#search-article`) đều được xây bằng component Vue phía client (Headless UI listbox, `vue-datepicker`, nút "Tìm kiếm" là `<a>` không có `action=`/`method=` — không phải `<form>` tĩnh). Đã thử 3 kiểu URL phân trang phổ biến (`?page=2`, `/page/2`, `?p=2`) — cả 3 đều bị Incapsula (WAF) chặn, trả về trang challenge JS rỗng thay vì nội dung thật, kể cả khi thử lại cẩn thận với delay dài hơn + header `Referer`. Quyết định: mỗi chuyên mục chỉ lấy đúng 10 bài mới nhất hiện có trên trang 1, KHÔNG cố dò thêm API/param ẩn (tránh giống hành vi né WAF của site .gov.vn thật) — xem Task 5 để ghi việc này vào CLAUDE.md như hướng mở rộng tương lai

**Tech Stack:** Python, pytest, httpx.MockTransport, Alembic, BeautifulSoup/soupsieve CSS selector

---

## Kết quả nghiên cứu thật (curl trực tiếp 2026-07-07, không phải suy đoán)

7 URL chuyên mục thật (lấy từ link trên trang chủ `bocongan.gov.vn`, đã fetch từng URL, cả 7 đều trả HTTP 200):

```
https://bocongan.gov.vn/chuyen-muc/chi-dao-dieu-hanh
https://bocongan.gov.vn/chuyen-muc/hoat-dong-cua-bo-cong-an-1754966863
https://bocongan.gov.vn/chuyen-muc/hoat-dong-cua-dia-phuong-1753170286
https://bocongan.gov.vn/chuyen-muc/hoat-dong-xa-hoi-1753170294
https://bocongan.gov.vn/chuyen-muc/nguoi-tot-viec-tot-1753170210
https://bocongan.gov.vn/chuyen-muc/thong-tin-doi-ngoai-1751367399
https://bocongan.gov.vn/chuyen-muc/tin-an-ninh-trat-tu-1753170263
```

> **Rủi ro đã biết:** 6/7 slug có hậu tố số (dạng timestamp, VD `-1754966863`) do site tự sinh — nếu bocongan.gov.vn tái cấu trúc menu chuyên mục sau này, các slug này có thể đổi và cần lấy lại qua curl. Không phải rủi ro cần xử lý ngay, chỉ ghi nhận.

Cấu trúc HTML mỗi trang chuyên mục có 3 loại "card" khác nhau: `card-large` (10 item), `card-medium` (2 item), `card-small` (38 item). Đã verify chính xác qua vị trí DOM (không chỉ đếm số lượng):

```
<div class="lg:col-span-8">  ← CỘT CHÍNH (8/12 grid)
  <h3 class="category-title">{Tên chuyên mục hiện tại}</h3>
  10× <article class="card-large">   ← 10 bài MỚI NHẤT của CHÍNH chuyên mục đang xem
  <select>10/20</select> ... "of 193 pages"   ← có pager thật, nhưng JS-driven (xem Architecture)

<div class="lg:col-span-4">  ← CỘT PHỤ bên phải (sidebar, 4/12 grid)
  <section><h3>Tin tức mới cập nhật</h3>      ← widget CHUNG toàn site, KHÔNG liên quan chuyên mục
    1× card-medium + nhiều× card-small
  <section><h3>Tin đọc nhiều trong tuần</h3>  ← widget CHUNG toàn site, KHÔNG liên quan chuyên mục
    1× card-medium + nhiều× card-small
```

Quyết định: **chỉ lấy `card-large`** (10 item trong cột chính) vì đây là danh sách bài THẬT của chính chuyên mục đang crawl; `card-medium`/`card-small` nằm trong sidebar là widget site-wide (không lọc theo chuyên mục), lấy vào sẽ gây trùng lặp/sai giữa 7 lần crawl (cùng 1 bài "Tin đọc nhiều trong tuần" xuất hiện lặp lại ở cả 7 trang chuyên mục).

**Cấu trúc `card-large` thật (đồng nhất 100% trên cả 7 trang, đã đếm chính xác 10 item/trang, thứ tự giảm dần theo ngày đã verify: 06/07 → 01/07 → 29/06 → 26/06 → 24/06 → 22/06 → 11/06 → 10/06 → 01/06 → 28/05/2026):**
```html
<article class="card-large ...">
  <figure>
    <a href="/bai-viet/lanh-dao-bo-cong-an-gui-thu-khen-...-1783311539"><picture>...</picture></a>
    <figcaption class="card-content ...">
      <a href="/bai-viet/lanh-dao-bo-cong-an-gui-thu-khen-...-1783311539"><h2>...</h2></a>
      <p class="... text-bca-gray-700 ...">Tóm tắt...</p>
      <span class="hidden lg:block text-bca-gray-700 text-xs">06/07/2026</span>
    </figcaption>
  </figure>
</article>
```
(2 thẻ `<a>` trong 1 item, cùng href — `select_one` lấy thẻ đầu tiên là đủ; `<p>` tóm tắt cũng có class `text-bca-gray-700` nên `listing_date` PHẢI chỉ định tag `span` để không nhầm)

**Selector thật đã verify (đã đếm lại đúng 10/10 trên `card-large`, không lẫn `<p>` tóm tắt):**
- `listing_item`: `article.card-large`
- `listing_link`: `a[href^="/bai-viet/"]`
- `listing_date`: `span.text-bca-gray-700`

Bài viết mẫu đã curl trực tiếp (`/bai-viet/lanh-dao-bo-cong-an-gui-thu-khen-...-1783311539`) xác nhận: có `og:title` (SSR, không cần Playwright — khớp quyết định cũ), **KHÔNG có** meta `article:published_time`, nhưng có JSON-LD `"datePublished":"2026-07-06T04:18:59.398Z"` — giải thích đúng hiện tượng `published_at=NULL` đã ghi ở Slice 2.

**Giới hạn đã biết (chấp nhận cho lần này, xem Architecture):** mỗi chuyên mục chỉ lấy tối đa 10 bài mới nhất/job (không phân trang) → tối đa 70 candidate/job trước khi lọc theo date range. Với 10 bài trải ~40 ngày (28/05 → 06/07 ở ví dụ trên), date range ngắn/trung (7-30 ngày) đủ phủ; date range rộng (90-150 ngày) có thể thiếu bài ở chuyên mục đăng ít — không phải lỗi, chỉ là giới hạn MVP.

---

## Mapping file → trách nhiệm sau khi sửa

| File | Thay đổi |
|---|---|
| `backend/crawler/listing.py` | `_fetch_one_listing_page`: thêm `urljoin` cho href tương đối (không cần đổi logic chọn `listing_link`, `card-large` dùng đúng pattern cũ) |
| `backend/tests/test_listing.py` | Thêm test cho href tương đối được `urljoin` thành URL tuyệt đối |
| `backend/workers/report_job.py` | `_crawl_sources`: fallback `published_at` về `candidate["lastmod"]` khi `parsed["published_at"]` là `None` |
| `backend/tests/test_report_job.py` | Thêm 2 test: fallback khi thiếu, ưu tiên giá trị thật khi có cả 2 |
| `backend/alembic/versions/0005_bocongan_listing_pages.py` (mới) | Migration cập nhật `parsing_rules` thật (7 URL + 2 selector) + xoá `sitemap_url` cho `bocongan.gov.vn` |
| `CLAUDE.md` | Cập nhật log sau khi verify xong (Task 4) |

**Lưu ý về commit:** theo yêu cầu, KHÔNG tạo git commit trong quá trình thực hiện plan này — để nguyên trong working tree cùng các thay đổi Giai đoạn A đang chờ, gộp commit sau khi có xác nhận.

---

## Task 1 — `listing.py`: `urljoin` cho href tương đối

**Files:**
- Modify: `backend/crawler/listing.py:1-9` (import), `backend/crawler/listing.py:58-69` (`_fetch_one_listing_page`)
- Test: `backend/tests/test_listing.py`

- [ ] **Step 1.1: Viết failing test**

Thêm vào cuối `backend/tests/test_listing.py`:

```python
class FakeRelativeHrefSource:
    listing_url = "https://bocongan.gov.vn/chuyen-muc/chi-dao-dieu-hanh"
    parsing_rules = {
        "listing_item": "article.card-large",
        "listing_link": 'a[href^="/bai-viet/"]',
        "listing_date": "span.date",
    }


def test_resolves_relative_href_against_listing_page_url():
    html = """
    <article class="card-large">
        <a href="/bai-viet/bai-trong-khoang"><h2>Bai trong khoang</h2></a>
        <span class="date">15/06/2026</span>
    </article>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed = get_listing_urls(
        FakeRelativeHrefSource(), date_from=date(2026, 1, 1), date_to=date(2026, 12, 31), client=client
    )

    # href tương đối "/bai-viet/..." phải được urljoin với listing_url thành URL tuyệt đối
    assert [item["url"] for item in result] == ["https://bocongan.gov.vn/bai-viet/bai-trong-khoang"]
    assert failed == []
```

- [ ] **Step 1.2: Chạy test, xác nhận FAIL**

Run: `cd backend && python -m pytest tests/test_listing.py::test_resolves_relative_href_against_listing_page_url -v`
Expected: FAIL — `assert ["/bai-viet/bai-trong-khoang"] == ["https://bocongan.gov.vn/bai-viet/bai-trong-khoang"]` (code hiện tại trả thẳng href gốc, không ghép domain)

- [ ] **Step 1.3: Sửa `backend/crawler/listing.py`**

Thêm import ở đầu file (dòng 1-8):
```python
import logging
import os
import re
import time
from datetime import date
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
```

Sửa 2 dòng trong `_fetch_one_listing_page` (thay thế đoạn hiện có ở dòng 66-67):
```python
        # urljoin xử lý cả 2 trường hợp: href tuyệt đối (tingia.gov.vn, giữ nguyên) và
        # tương đối (bocongan.gov.vn, ghép với URL trang danh sách đang fetch)
        href = link_el.get("href")
        item_url = urljoin(url, href) if href else None
        published = _parse_listing_date(date_el.get_text(strip=True))
```

(Xoá comment cũ "Giả định href là URL tuyệt đối..." vì không còn đúng — nay xử lý cả 2 trường hợp)

- [ ] **Step 1.4: Chạy lại test mới, xác nhận PASS**

Run: `cd backend && python -m pytest tests/test_listing.py::test_resolves_relative_href_against_listing_page_url -v`
Expected: PASS

- [ ] **Step 1.5: Chạy toàn bộ `test_listing.py`, xác nhận không có test cũ bị break**

Run: `cd backend && python -m pytest tests/test_listing.py -v`
Expected: tất cả PASS (bao gồm các test tingia.gov.vn cũ — `urljoin` không đổi hành vi khi href đã tuyệt đối)

---

## Task 2 — `report_job.py`: fallback `published_at` về `candidate["lastmod"]`

**Files:**
- Modify: `backend/workers/report_job.py:105-119`
- Test: `backend/tests/test_report_job.py`

- [ ] **Step 2.1: Viết failing test**

Thêm vào cuối `backend/tests/test_report_job.py`:

```python
def test_crawl_sources_falls_back_to_listing_lastmod_when_published_at_missing(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    candidates = [{"url": "https://example.test/bai-viet/a", "lastmod": date(2026, 6, 15)}]

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url,
            "url_hash": f"hash-{url}",
            "title": "Title",
            "content_raw": "Content",
            "author": None,
            "published_at": None,  # giống bocongan.gov.vn thật: thiếu meta article:published_time
            "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        article = db_session.query(Article).filter_by(job_id=job.job_id).one()
        assert article.published_at == datetime(2026, 6, 15, 0, 0)
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_prefers_parsed_published_at_over_listing_lastmod(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    candidates = [{"url": "https://example.test/bai-viet/a", "lastmod": date(2026, 6, 15)}]

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url,
            "url_hash": f"hash-{url}",
            "title": "Title",
            "content_raw": "Content",
            "author": None,
            "published_at": datetime(2026, 6, 20, 8, 0),  # có giá trị thật từ chính bài viết
            "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        article = db_session.query(Article).filter_by(job_id=job.job_id).one()
        # published_at thật từ bài viết phải được ưu tiên hơn lastmod của trang danh sách
        assert article.published_at == datetime(2026, 6, 20, 8, 0)
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()
```

- [ ] **Step 2.2: Chạy 2 test mới, xác nhận FAIL**

Run: `cd backend && python -m pytest tests/test_report_job.py::test_crawl_sources_falls_back_to_listing_lastmod_when_published_at_missing tests/test_report_job.py::test_crawl_sources_prefers_parsed_published_at_over_listing_lastmod -v`
Expected: test đầu FAIL (`article.published_at` là `None`, không phải `datetime(2026, 6, 15, 0, 0)`); test thứ hai PASS sẵn (không thay đổi hành vi ưu tiên) — vẫn chạy để lock lại hành vi trước khi sửa

- [ ] **Step 2.3: Sửa `backend/workers/report_job.py`**

Thay khối sau (dòng 105-119 hiện tại):
```python
            published_at = parsed.get("published_at")
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
                    published_at=parsed["published_at"],
                    crawl_duration_seconds=parsed.get("crawl_duration_seconds"),
                )
            )
            db.commit()
```

bằng:
```python
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

- [ ] **Step 2.4: Chạy lại 2 test, xác nhận PASS**

Run: `cd backend && python -m pytest tests/test_report_job.py::test_crawl_sources_falls_back_to_listing_lastmod_when_published_at_missing tests/test_report_job.py::test_crawl_sources_prefers_parsed_published_at_over_listing_lastmod -v`
Expected: cả 2 PASS

- [ ] **Step 2.5: Chạy toàn bộ `test_report_job.py`, xác nhận không break test cũ**

Run: `cd backend && python -m pytest tests/test_report_job.py -v`
Expected: tất cả PASS

---

## Task 3 — Migration: parsing_rules thật + xoá sitemap_url cho bocongan.gov.vn

**Files:**
- Create: `backend/alembic/versions/0005_bocongan_listing_pages.py`

- [ ] **Step 3.1: Viết migration**

```python
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
```

- [ ] **Step 3.2: Chạy migration thật, xác nhận DB cập nhật đúng**

Run: `docker compose exec backend alembic upgrade head`
Expected: chạy không lỗi, log hiện `0004 -> 0005`

Run: `docker compose exec postgres psql -U <user> -d ngs_monitor -c "SELECT domain, sitemap_url, parsing_rules FROM sources WHERE domain='bocongan.gov.vn';"`
Expected: `sitemap_url` là `NULL`, `parsing_rules` chứa đủ `listing_item`/`listing_link`/`listing_date`/`listing_pages` (7 URL) + vẫn giữ `engine: crawl4ai`

- [ ] **Step 3.3: Xác nhận `downgrade` phục hồi đúng trạng thái cũ (an toàn khi cần rollback)**

Run: `docker compose exec backend alembic downgrade 0004 && docker compose exec backend alembic upgrade head`
Expected: không lỗi; sau khi upgrade lại, `SELECT` ở Step 3.2 vẫn cho kết quả đúng như cũ

---

## Task 4 — Verify job thật end-to-end

**Không có file thay đổi — chỉ chạy job thật để xác nhận toàn bộ thay đổi hoạt động đúng với dữ liệu thật.**

- [ ] **Step 4.1: Tạo job thật chỉ với bocongan.gov.vn, khoảng ngày hẹp**

```bash
curl -X POST http://localhost:8000/api/reports/create \
  -H "Content-Type: application/json" \
  -d '{"source_ids": ["00000000-0000-0000-0000-000000000005"], "date_from": "2026-06-20", "date_to": "2026-07-07"}'
```

Ghi lại `job_id` trả về.

- [ ] **Step 4.2: Đặt `MAX_ARTICLES_PER_JOB` thấp trước khi chạy (nếu chưa đặt trong `.env`) để giới hạn thời gian chạy AI CPU-only**

Xác nhận biến môi trường `MAX_ARTICLES_PER_JOB` (VD `4`) đã áp dụng cho `celery-worker` — theo đúng cách đã làm ở lần verify Slice 2 trước.

- [ ] **Step 4.3: Poll status tới khi `completed`**

```bash
curl http://localhost:8000/api/reports/<job_id>/status
```

Expected: cuối cùng `status: "completed"`, `progress.crawled` > 0

- [ ] **Step 4.4: Xác nhận `published_at` KHÔNG còn NULL — đây là phép thử trực tiếp cho Task 2**

```bash
docker compose exec postgres psql -U <user> -d ngs_monitor -c \
  "SELECT url, published_at, status FROM articles WHERE job_id='<job_id>';"
```

Expected: mọi article `status != 'error'` có `published_at` khác `NULL` (lấy từ listing lastmod nếu bài viết tự nó không có, hoặc từ crawl4ai nếu có)

- [ ] **Step 4.5: Xác nhận output hợp lệ**

```bash
curl http://localhost:8000/api/reports/<job_id>/download -o /tmp/claude-1000/bocongan_verify.docx
file /tmp/claude-1000/bocongan_verify.docx
```

Expected: `Microsoft Word 2007+`, không rỗng; `jobs.output_json` cũng tồn tại và là JSON hợp lệ

- [ ] **Step 4.6: Kiểm tra log worker không có exception**

```bash
docker compose logs celery-worker --tail 200 | grep -i "error\|exception\|traceback"
```

Expected: không có exception liên quan tới `bocongan.gov.vn` (nếu có warning `selector không khớp item nào` cần điều tra lại selector)

---

## Task 5 — Cập nhật CLAUDE.md sau khi verify xong

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 5.1:** Cập nhật "Trạng thái hiện tại": đổi dòng "BoCongAn sitemap thay thế: Giai đoạn A xong... Giai đoạn B chưa bắt đầu" thành đã hoàn thành, ghi kết quả verify thật (số bài, published_at không còn NULL)
- [ ] **Step 5.2:** Xoá/cập nhật mục "CSS selector cho 7 trang chuyên mục... chưa được viết" khỏi "Vấn đề cần làm rõ" — đã giải quyết. Đồng thời sửa lại số ước tính sai "~37-40 bài mới nhất" (dựa trên card-small nhầm) thành đúng: mỗi chuyên mục chỉ lấy 10 bài mới nhất (`card-large`), tối đa 70 candidate/job trước khi lọc theo date range
- [ ] **Step 5.3:** Thêm các dòng quyết định mới vào bảng "Quyết định quan trọng":
  - Chỉ lấy `article.card-large` (10 bài/chuyên mục, đúng nội dung chuyên mục đang crawl) — bỏ qua `card-medium`/`card-small` vì đó là 2 widget site-wide ("Tin tức mới cập nhật"/"Tin đọc nhiều trong tuần") nằm ở sidebar, không liên quan chuyên mục đang xem, lấy vào sẽ trùng lặp giữa cả 7 lần crawl
  - Fallback `published_at` về listing lastmod khi bài viết tự nó không có (`crawl4ai` thiếu `article:published_time`) thay vì sửa `crawl4ai_client.py` đọc JSON-LD — tái dùng dữ liệu ngày đã lấy từ trang danh sách, đơn giản hơn
  - **Không làm phân trang (`?page=N`) lẫn form lọc theo ngày ("Từ ngày"/"Đến ngày") của bocongan.gov.vn trong lần cải tiến này** — cả 2 đều là tính năng JS phía client (Vue Headless UI listbox + `vue-datepicker`, nút "Tìm kiếm" là `<a>` không có `action=`/`method=` tĩnh), không phải URL/form có thể gọi trực tiếp bằng `httpx`. Đã thử 3 kiểu URL phân trang phổ biến (`?page=2`, `/page/2`, `?p=2`, kể cả thử lại cẩn thận với delay dài + header `Referer`) — cả 3 đều bị Incapsula (WAF) chặn, trả về trang challenge JS thay vì nội dung thật. Quyết định dừng dò thêm (tránh giống hành vi né WAF của site .gov.vn thật). **Hướng mở rộng tương lai (chưa làm):** cần người dùng tự inspect tab Network trên trình duyệt thật khi bấm "Tìm kiếm"/chuyển trang để lấy API thật (endpoint/param/header), từ đó mới biết có gọi được bằng `httpx` hay bắt buộc cần Playwright
- [ ] **Step 5.4:** Cập nhật "Bước tiếp theo": bỏ mục BoCongAn Giai đoạn B, chuyển focus sang Slice 3. Thêm ghi chú "tương lai" riêng (không phải bước tiếp theo ngay): mở rộng độ phủ lịch sử của bocongan.gov.vn qua phân trang/lọc ngày thật — cần API thật lấy từ Network tab trước khi làm được (xem Step 5.3)

---

## Self-Review

**Spec coverage:** Task 1+3 giải quyết "CSS selector thật + migration" (yêu cầu gốc trong CLAUDE.md "Bước tiếp theo"), nay dùng đúng selector `card-large` sau khi người dùng chỉ ra và verify lại bằng HTML thật (bản nháp đầu lấy nhầm `card-small`/sidebar). Task 4 giải quyết "chạy job thật để verify". Task 2 giải quyết phát hiện mới (published_at) nêu ra từ câu hỏi của người dùng. Task 5 đóng vòng lặp cập nhật tài liệu, gồm cả việc ghi nhận rõ quyết định KHÔNG làm phân trang/lọc ngày (chặn bởi kiến trúc JS-client + WAF) làm hướng mở rộng tương lai.

**Placeholder scan:** không còn "TBD"/"tương tự Task N" — mọi step đều có code/lệnh cụ thể.

**Type consistency:** `candidate["lastmod"]` luôn là `date` (từ `_parse_listing_date`/`_parse_lastmod`), convert bằng `datetime.combine(...)` khớp kiểu cột `TIMESTAMP`. `item_url`/`href` dùng nhất quán tên biến giữa Task 1 và test. Selector `listing_item`/`listing_link`/`listing_date` nhất quán giữa phần "Kết quả nghiên cứu thật", Task 1 test, và Task 3 migration.

---

**Plan complete and saved to `docs/superpowers/plans/2026-07-07-bocongan-giai-doan-b.md`.**

Lưu ý: theo yêu cầu, **không** tạo git commit khi thực hiện các task trên — để nguyên trong working tree.

Hai lựa chọn thực thi:
1. **Subagent-Driven (khuyến nghị)** — dispatch subagent riêng cho từng task, review giữa các task
2. **Inline Execution** — thực thi tuần tự trong session hiện tại, có checkpoint để bạn xem lại

Bạn muốn theo cách nào?
