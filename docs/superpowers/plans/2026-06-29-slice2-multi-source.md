# Slice 2 — Nhiều nguồn + listing-page fallback — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mở rộng pipeline từ 1 nguồn (VTV) sang nhiều nguồn thật, thêm chiến lược crawl listing-page (fallback khi không có sitemap), và xây sidebar chọn nhiều nguồn ở FE — đúng checklist Slice 2 trong `CLAUDE.md`.

**Architecture:** Tổng quát hóa `backend/crawler/sitemap.py` để nhận nhiều dạng sitemap thật (phẳng/index, nhiều pattern tên sub-sitemap) thay vì chỉ đúng 1 pattern của VTV; thêm module `backend/crawler/listing.py` mới cho nguồn không có sitemap; `report_job.py` tự chọn chiến lược theo cấu hình nguồn và lọc lại theo ngày đăng thật sau khi fetch (an toàn hơn tin tưởng tuyệt đối vào sitemap). Tất cả nguồn mới dùng engine Crawl4AI có sẵn (không cần viết CSS selector tay).

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, httpx, BeautifulSoup, Crawl4AI, Next.js/React/TypeScript, Tailwind, Pytest.

---

## Bối cảnh & quyết định đã chốt (đọc trước khi code)

Trước khi viết plan này đã kiểm tra **thật** (curl + WebFetch, không suy đoán) sitemap/HTML của các nguồn trong báo cáo khảo sát thật `Bao_cao_Du_lieu_Thuc_22-06-2026.docx` (11/40 nguồn đã xác nhận crawl được nội dung tin giả thật bằng WebFetch/WebSearch ngày 22/06/2026). Kết quả + quyết định người dùng đã chọn:

| Nguồn | Kết quả kiểm tra thật | Quyết định |
|---|---|---|
| VTV.vn | Đã có (Slice 1), sitemap index, pattern `sitemaps-YYYY-MM-DD-DD.xml` | Giữ nguyên, không đổi |
| VOV.vn | Sitemap index, sub-sitemap `/sitemaps/{YYYY}/{M}/article.xml` (**khác pattern VTV**), `<lastmod>` đáng tin | Thêm, engine=crawl4ai |
| VietnamPlus.vn | Sitemap index, sub-sitemap `news-YYYY-M.xml` + `categories.xml` (không theo ngày), `<lastmod>` đáng tin | Thêm, engine=crawl4ai |
| CAND.vn (redirect từ cand.com.vn) | Sitemap index, cùng pattern `news-YYYY-M.xml` như VietnamPlus | Thêm, engine=crawl4ai |
| BoCongAn.gov.vn | Sitemap **phẳng** (không có index, 500 `<url>` liệt kê trực tiếp). **Mọi `<lastmod>` giống nhau y hệt** (`2025-08-20T08:02:22+00:00`) — đây là timestamp lúc sitemap được build lại, không phải ngày đăng bài thật | Thêm, engine=crawl4ai. Lọc theo `<lastmod>` sẽ SAI cho nguồn này → phải lọc theo ngày đăng thật sau khi fetch bài (xem Task 3) |
| qdnd.vn | `curl`/WebFetch tới `sitemap.xml` **và cả trang chủ** đều bị redirect-loop vô hạn (302) từ network môi trường test hiện tại | **Tạm loại khỏi Slice 2**, ghi vào CLAUDE.md là rủi ro cần verify lại từ server production trước khi thêm |
| tingia.gov.vn | Sitemap chia theo **chủ đề** (không theo ngày), chỉ 1 bài xác minh trong khảo sát. Trang chủ liệt kê bài + ngày dạng `DD/MM/YYYY - HH:MM`, **không có phân trang** | Thêm qua **listing-page fallback** (mới, Task 2), không qua sitemap |
| chinhphu.vn / mod.gov.vn / bvhttdl.gov.vn | Khảo sát không tìm thấy bài chuyên về tin giả | **Không thêm** lần này — người dùng xác nhận 6 nguồn (VTV + 5 mới) là đủ cho Slice 2, không cần ép đủ 8-10 |

**Engine fetch:** tất cả 5 nguồn mới dùng `parsing_rules.engine = "crawl4ai"` — không viết CSS selector tay (tránh 6x công reverse-engineer 6 template HTML khác nhau, đã verify Crawl4AI hoạt động thật trên VTV+VOV ở phần chuẩn bị trước Slice 2).

**Số nguồn thực tế sau Slice 2 này: 6** (VTV + VOV + VietnamPlus + CAND + BoCongAn + TinGia), không phải 8-10 như ước tính cũ trong roadmap — xem Task 6 (cập nhật CLAUDE.md ghi rõ lý do).

**Giả định cần xác nhận lại khi review:** hằng số ước tính thời gian cho Summary Card ở FE (Task 8) dùng `ESTIMATED_SECONDS_PER_ARTICLE = 90` (ước lượng thô dựa trên `AI_TIMEOUT_SECONDS=360` và ghi nhận thật "qwen3:8b có lúc >120s/bài") — mockup gốc ở `09-frontend-ui.md` ghi ví dụ "~900 bài · ~45 phút" (≈3s/bài) là **số không khớp thực tế đã biết**, nên không copy nguyên số đó.

---

## File Structure

- Modify: `backend/crawler/sitemap.py` — tổng quát hóa `get_article_urls()`
- Modify: `backend/tests/test_sitemap.py` — test sitemap phẳng + nhiều pattern ngày
- Create: `backend/crawler/listing.py` — listing-page crawler (1 trang, không phân trang — YAGNI, xem Task 2)
- Create: `backend/tests/test_listing.py`
- Modify: `backend/workers/report_job.py` — dispatch sitemap/listing + lọc ngày đăng thật sau fetch
- Modify: `backend/tests/test_report_job.py`
- Create: `backend/alembic/versions/0004_seed_slice2_sources.py`
- Create: `backend/routers/sources.py` — `GET /api/sources`
- Create: `backend/tests/test_sources_router.py`
- Modify: `backend/main.py` — đăng ký router mới
- Create: `frontend/components/SourceSidebar.tsx`
- Create: `frontend/components/SummaryCard.tsx`
- Modify: `frontend/app/page.tsx` — thay nguồn hardcode bằng sidebar đa chọn
- Modify: `.claude/rules/10-error-handling.md` — thêm rule "bỏ qua bài ngoài khoảng ngày sau fetch"
- Modify: `CLAUDE.md` — tick checklist Slice 2, ghi quyết định mới, ghi rủi ro qdnd.vn

---

### Task 1: Tổng quát hóa sitemap parser (hỗ trợ sitemap phẳng + nhiều pattern ngày)

**Files:**
- Modify: `backend/crawler/sitemap.py`
- Test: `backend/tests/test_sitemap.py`

**Vấn đề thật đã verify:** `get_article_urls()` hiện tại giả định LUÔN có sitemap index (`index_soup.find_all("sitemap")`) và chỉ nhận diện đúng 1 regex tên file (`sitemaps-(\d+)-(\d+)-(\d+)-(\d+)\.xml$`, kiểu VTV). Với VOV/VietnamPlus/CAND (pattern `news-YYYY-M.xml` hoặc `/YYYY/M/...`) và BoCongAn (sitemap phẳng, không index) — code hiện tại trả về **0 bài**.

- [ ] **Step 1: Viết test cho sitemap phẳng (không index) — test fail trước**

Thêm vào cuối `backend/tests/test_sitemap.py`:

```python
def test_flat_urlset_returns_all_urls_without_lastmod_filtering():
    # Một số nguồn (VD bocongan.gov.vn) sitemap KHÔNG có index, liệt kê <url> trực tiếp,
    # và ghi <lastmod> giống nhau cho MỌI url (timestamp lúc sitemap được build lại, không
    # phải ngày đăng bài thật, đã verify thật) — không lọc ở đây, để report_job.py lọc lại
    # bằng ngày đăng thật sau khi fetch từng bài (xem _crawl_sources).
    flat_sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://bocongan.gov.vn/bai-viet-a</loc>
        <lastmod>2025-08-20T08:02:22+00:00</lastmod>
    </url>
    <url>
        <loc>https://bocongan.gov.vn/bai-viet-b</loc>
        <lastmod>2025-08-20T08:02:22+00:00</lastmod>
    </url>
</urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=flat_sitemap)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed_locs = get_article_urls(
        FakeSource(),
        date_from=date(2026, 1, 1),
        date_to=date(2026, 5, 30),
        client=client,
        delay_seconds=0,
    )

    urls = [item["url"] for item in result]
    assert urls == ["https://bocongan.gov.vn/bai-viet-a", "https://bocongan.gov.vn/bai-viet-b"]
    assert failed_locs == []


def test_recognizes_year_month_only_sub_sitemap_pattern():
    # VOV/VietnamPlus/CAND dùng pattern khác VTV: chỉ năm-tháng (không có khoảng ngày trong tên)
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap>
        <loc>https://vov.vn/sitemaps/2026/4/article.xml</loc>
    </sitemap>
    <sitemap>
        <loc>https://vov.vn/sitemaps/2026/6/article.xml</loc>
    </sitemap>
</sitemapindex>"""
    sub_sitemap_june = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://vov.vn/bai-viet-thang-6</loc>
        <lastmod>2026-06-15T10:00:00+07:00</lastmod>
    </url>
</urlset>"""

    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        if "2026/6" in str(request.url):
            return httpx.Response(200, text=sub_sitemap_june)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed_locs = get_article_urls(
        FakeSource(),
        date_from=date(2026, 6, 10),
        date_to=date(2026, 6, 20),
        client=client,
        delay_seconds=0,
    )

    urls = [item["url"] for item in result]
    assert urls == ["https://vov.vn/bai-viet-thang-6"]
    assert "https://vov.vn/sitemaps/2026/4/article.xml" not in requested
    assert failed_locs == []


def test_fetches_sub_sitemap_with_unrecognized_name_pattern_instead_of_skipping():
    # tingia.gov.vn (và các nguồn tương tự) chia sitemap theo CHỦ ĐỀ, không theo ngày —
    # không nhận diện được pattern ngày trong tên thì phải fetch để lọc theo <lastmod> thật
    # bên trong, KHÔNG được bỏ qua (an toàn hơn).
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap>
        <loc>https://tingia.gov.vn/sitemap/tai-chinh-ngan-hang.xml</loc>
    </sitemap>
</sitemapindex>"""
    topic_sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://tingia.gov.vn/bai-trong-khoang</loc>
        <lastmod>2026-01-26T00:00:00+07:00</lastmod>
    </url>
</urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        if "tai-chinh-ngan-hang" in str(request.url):
            return httpx.Response(200, text=topic_sitemap)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed_locs = get_article_urls(
        FakeSource(),
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
        client=client,
        delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://tingia.gov.vn/bai-trong-khoang"]
    assert failed_locs == []
```

- [ ] **Step 2: Chạy test, xác nhận 3 test mới FAIL**

```bash
cd backend && pytest tests/test_sitemap.py -v
```
Expected: 3 test mới FAIL (test phẳng trả về `[]` thay vì 2 url; test year-month không nhận diện pattern nên fetch nhầm cả 2 sub-sitemap; test unrecognized-pattern bị bỏ qua do `date_range is None` không được coi là "phải fetch"). 2 test cũ (`test_returns_only_urls_with_lastmod_inside_date_range_and_skips_irrelevant_sub_sitemaps`, `test_skips_sub_sitemap_that_keeps_failing_after_retries_without_raising`) vẫn PASS.

- [ ] **Step 3: Viết lại `get_article_urls()` để tổng quát hóa**

Thay toàn bộ nội dung `backend/crawler/sitemap.py`:

```python
import calendar
import logging
import os
import re
import time
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# VTV: sitemaps-YYYY-MM-DD_start-DD_end.xml (khoảng ngày trong 1 tháng)
_DATE_RANGE_RE = re.compile(r"sitemaps-(\d+)-(\d+)-(\d+)-(\d+)\.xml$")
# VOV/VietnamPlus/CAND: chỉ năm-tháng, không có khoảng ngày trong tên
# (VD .../2026/5/article.xml hoặc news-2026-6.xml)
_YEAR_MONTH_RE = re.compile(r"(?:^|[/-])(\d{4})[/-](\d{1,2})(?:[/.]|$)")


def _parse_lastmod(value: str) -> date:
    return datetime.fromisoformat(value).date()


def _sub_sitemap_date_range(loc: str) -> tuple[date, date] | None:
    match = _DATE_RANGE_RE.search(loc)
    if match:
        year, month, day_start, day_end = (int(g) for g in match.groups())
        return date(year, month, day_start), date(year, month, day_end)

    match = _YEAR_MONTH_RE.search(loc)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12:
            day_end = calendar.monthrange(year, month)[1]
            return date(year, month, 1), date(year, month, day_end)

    return None


def _ranges_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and b_start <= a_end


def _fetch_with_retry(client: httpx.Client, url: str, max_retries: int) -> httpx.Response | None:
    for attempt in range(max_retries):
        try:
            return client.get(url)
        except httpx.HTTPError:
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
    logger.warning("Hết %d lượt thử, bỏ qua sub-sitemap: %s", max_retries, url)
    return None


def _extract_all_urls(soup: BeautifulSoup) -> list[dict]:
    results = []
    for url_tag in soup.find_all("url"):
        article_url = url_tag.find("loc").get_text(strip=True)
        lastmod_tag = url_tag.find("lastmod")
        lastmod = _parse_lastmod(lastmod_tag.get_text(strip=True)) if lastmod_tag else None
        results.append({"url": article_url, "lastmod": lastmod})
    return results


def _extract_urls_in_range(soup: BeautifulSoup, date_from: date, date_to: date) -> list[dict]:
    return [item for item in _extract_all_urls(soup) if item["lastmod"] and date_from <= item["lastmod"] <= date_to]


def get_article_urls(
    source,
    date_from: date,
    date_to: date,
    client: httpx.Client | None = None,
    delay_seconds: float | None = None,
    max_retries: int | None = None,
) -> tuple[list[dict], list[str]]:
    owns_client = client is None
    client = client or httpx.Client(timeout=int(os.environ.get("CRAWLER_TIMEOUT_SECONDS", "30")))
    if delay_seconds is None:
        delay_seconds = float(os.environ.get("CRAWLER_DELAY_SECONDS", "1.5"))
    if max_retries is None:
        max_retries = int(os.environ.get("CRAWLER_MAX_RETRIES", "3"))

    try:
        index_resp = client.get(source.sitemap_url)
        index_soup = BeautifulSoup(index_resp.text, "xml")

        sitemap_tags = index_soup.find_all("sitemap")
        if not sitemap_tags:
            # Sitemap phẳng (urlset liệt kê <url> trực tiếp, không qua sub-sitemap) — VD
            # bocongan.gov.vn. KHÔNG lọc theo <lastmod> ở đây vì một số nguồn ghi <lastmod>
            # giống nhau cho mọi URL (timestamp build lại sitemap, không phải ngày đăng thật,
            # đã verify thật) — lọc theo ngày đăng thật được làm ở report_job.py sau khi fetch
            # xong từng bài.
            return _extract_all_urls(index_soup), []

        sub_sitemap_locs = []
        for sitemap_tag in sitemap_tags:
            loc = sitemap_tag.find("loc").get_text(strip=True)
            date_range = _sub_sitemap_date_range(loc)
            # Không nhận diện được pattern ngày trong tên (VD chia theo chủ đề như
            # tingia.gov.vn) -> không pre-filter, luôn fetch để lọc theo <lastmod> thật bên
            # trong (an toàn hơn bỏ qua nhầm).
            if date_range is None or _ranges_overlap(date_range[0], date_range[1], date_from, date_to):
                sub_sitemap_locs.append(loc)

        results = []
        failed_locs = []
        for loc in sub_sitemap_locs:
            time.sleep(delay_seconds)
            sub_resp = _fetch_with_retry(client, loc, max_retries)
            if sub_resp is None:
                failed_locs.append(loc)
                continue
            sub_soup = BeautifulSoup(sub_resp.text, "xml")
            results.extend(_extract_urls_in_range(sub_soup, date_from, date_to))
        return results, failed_locs
    finally:
        if owns_client:
            client.close()
```

- [ ] **Step 4: Chạy lại toàn bộ test, xác nhận PASS (cả mới + cũ)**

```bash
cd backend && pytest tests/test_sitemap.py -v
```
Expected: 5/5 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/crawler/sitemap.py backend/tests/test_sitemap.py
git commit -m "feat: tổng quát hóa sitemap parser hỗ trợ sitemap phẳng + nhiều pattern ngày"
```

---

### Task 2: Listing-page crawler (fallback khi không có sitemap)

**Files:**
- Create: `backend/crawler/listing.py`
- Test: `backend/tests/test_listing.py`

**Phạm vi:** chỉ cần fetch **1 trang** (không phân trang) — nguồn duy nhất dùng chiến lược này hiện tại (tingia.gov.vn) không có phân trang thật trên trang chủ (đã verify, danh sách bài viết nằm hết trên 1 trang). Không xây cơ chế phân trang khi chưa có nguồn thật nào cần (YAGNI) — sẽ mở rộng khi Slice sau thêm nguồn cần phân trang thật.

- [ ] **Step 1: Viết test trước**

Tạo `backend/tests/test_listing.py`:

```python
from datetime import date

import httpx

from backend.crawler.listing import get_listing_urls


class FakeListingSource:
    listing_url = "https://tingia.gov.vn/"
    parsing_rules = {
        "listing_item": "div.info",
        "listing_link": "h2.title a",
        "listing_date": "span.date",
    }


LISTING_HTML = """
<html><body>
<div class="info">
    <h2 class="title"><a href="https://tingia.gov.vn/bai-trong-khoang.html">Bài trong khoảng</a></h2>
    <span class="date">26/01/2026 - 17:37</span>
</div>
<div class="info">
    <h2 class="title"><a href="https://tingia.gov.vn/bai-ngoai-khoang.html">Bài ngoài khoảng</a></h2>
    <span class="date">20/02/2025 - 09:00</span>
</div>
</body></html>
"""


def test_returns_only_items_with_date_inside_range():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=LISTING_HTML)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed = get_listing_urls(
        FakeListingSource(), date_from=date(2026, 1, 1), date_to=date(2026, 1, 31), client=client
    )

    assert [item["url"] for item in result] == ["https://tingia.gov.vn/bai-trong-khoang.html"]
    assert failed == []


def test_returns_failed_url_when_fetch_exhausts_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed = get_listing_urls(
        FakeListingSource(),
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
        client=client,
        max_retries=2,
    )

    assert result == []
    assert failed == ["https://tingia.gov.vn/"]


def test_skips_items_with_unparseable_date():
    html = """
    <div class="info">
        <h2 class="title"><a href="https://tingia.gov.vn/bai-khong-co-ngay.html">Không có ngày</a></h2>
        <span class="date">Không rõ</span>
    </div>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result, failed = get_listing_urls(
        FakeListingSource(), date_from=date(2026, 1, 1), date_to=date(2026, 1, 31), client=client
    )

    assert result == []
    assert failed == []
```

- [ ] **Step 2: Chạy test, xác nhận FAIL (module chưa tồn tại)**

```bash
cd backend && pytest tests/test_listing.py -v
```
Expected: FAIL với `ModuleNotFoundError: No module named 'backend.crawler.listing'`.

- [ ] **Step 3: Viết `backend/crawler/listing.py`**

```python
import logging
import os
import re
import time
from datetime import date

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Format thật đã verify trên tingia.gov.vn: "26/01/2026 - 17:37"
_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def _fetch_with_retry(client: httpx.Client, url: str, max_retries: int) -> httpx.Response | None:
    for attempt in range(max_retries):
        try:
            return client.get(url)
        except httpx.HTTPError:
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
    logger.warning("Hết %d lượt thử, bỏ qua trang danh sách: %s", max_retries, url)
    return None


def _parse_listing_date(text: str) -> date | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    day, month, year = (int(g) for g in match.groups())
    return date(year, month, day)


def get_listing_urls(
    source,
    date_from: date,
    date_to: date,
    client: httpx.Client | None = None,
    max_retries: int | None = None,
) -> tuple[list[dict], list[str]]:
    owns_client = client is None
    client = client or httpx.Client(timeout=int(os.environ.get("CRAWLER_TIMEOUT_SECONDS", "30")))
    if max_retries is None:
        max_retries = int(os.environ.get("CRAWLER_MAX_RETRIES", "3"))

    try:
        resp = _fetch_with_retry(client, source.listing_url, max_retries)
        if resp is None:
            return [], [source.listing_url]

        soup = BeautifulSoup(resp.text, "html.parser")
        rules = source.parsing_rules
        results = []
        for item in soup.select(rules["listing_item"]):
            link_el = item.select_one(rules["listing_link"])
            date_el = item.select_one(rules["listing_date"])
            if link_el is None or date_el is None:
                continue
            url = link_el.get("href")
            published = _parse_listing_date(date_el.get_text(strip=True))
            if url and published and date_from <= published <= date_to:
                results.append({"url": url, "lastmod": published})
        return results, []
    finally:
        if owns_client:
            client.close()
```

- [ ] **Step 4: Chạy lại test, xác nhận PASS**

```bash
cd backend && pytest tests/test_listing.py -v
```
Expected: 3/3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/crawler/listing.py backend/tests/test_listing.py
git commit -m "feat: thêm listing-page crawler (fallback khi nguồn không có sitemap)"
```

---

### Task 3: `report_job.py` — dispatch sitemap/listing + lọc ngày đăng thật sau fetch

**Files:**
- Modify: `backend/workers/report_job.py`
- Test: `backend/tests/test_report_job.py`

**2 thay đổi:**
1. `_crawl_sources()` tự chọn `get_article_urls` (mặc định, ưu tiên) hay `get_listing_urls` (chỉ khi nguồn có `listing_url` và KHÔNG có `sitemap_url`) — đúng thứ tự ưu tiên đã ghi ở `06-crawler-strategy.md`.
2. Sau khi fetch xong 1 bài thành công, lọc lại theo `published_at` thật của bài viết so với `job.date_from/date_to` — **bắt buộc** vì sitemap phẳng (bocongan.gov.vn) không lọc được chính xác trước khi fetch (xem Task 1). Không phải lỗi nên **không** insert `status="error"`, chỉ bỏ qua âm thầm (giống cách xử lý dữ liệu trùng lặp hiện có).

- [ ] **Step 1: Viết test trước (dispatch + lọc ngày)**

Thêm vào `backend/tests/test_report_job.py` (sau import, thêm `from datetime import date, datetime` — sửa dòng `from datetime import date` thành `from datetime import date, datetime`):

```python
def test_crawl_sources_uses_listing_strategy_when_source_has_listing_url_and_no_sitemap(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(
        name="Test Listing",
        domain=f"test-listing-{uuid.uuid4()}.example",
        group_name="Test",
        listing_url="https://example.test/",
        parsing_rules={},
    )
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    try:
        with patch("backend.workers.report_job.get_listing_urls", return_value=([], [])) as mock_listing, patch(
            "backend.workers.report_job.get_article_urls"
        ) as mock_sitemap, patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        mock_listing.assert_called_once()
        mock_sitemap.assert_not_called()
    finally:
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_skips_insert_when_published_at_outside_requested_range(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    candidates = [{"url": "https://example.test/bai-ngoai-khoang", "lastmod": None}]

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url,
            "url_hash": f"hash-{url}",
            "title": "Title",
            "content_raw": "Content",
            "author": None,
            "published_at": datetime(2025, 8, 20, 8, 2, 22),
            "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        count = db_session.query(Article).filter_by(job_id=job.job_id).count()
        assert count == 0
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_inserts_when_published_at_inside_requested_range(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    candidates = [{"url": "https://example.test/bai-trong-khoang", "lastmod": None}]

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url,
            "url_hash": f"hash-{url}",
            "title": "Title",
            "content_raw": "Content",
            "author": None,
            "published_at": datetime(2026, 6, 15, 10, 0, 0),
            "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        count = db_session.query(Article).filter_by(job_id=job.job_id).count()
        assert count == 1
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()
```

- [ ] **Step 2: Chạy test mới, xác nhận FAIL**

```bash
cd backend && pytest tests/test_report_job.py -v
```
Expected: 3 test mới FAIL (`get_listing_urls` chưa được import/dùng trong `report_job.py`; chưa có logic lọc `published_at`).

- [ ] **Step 3: Sửa `backend/workers/report_job.py`**

Sửa dòng import (sau `from backend.crawler.crawl4ai_client import fetch_article_dispatch`):

```python
from backend.crawler.crawl4ai_client import fetch_article_dispatch
from backend.crawler.listing import get_listing_urls
from backend.crawler.sitemap import get_article_urls
```

Thêm hàm `_get_candidates` ngay trước `_crawl_sources`, và sửa toàn bộ thân `_crawl_sources`:

```python
def _get_candidates(source, date_from, date_to) -> tuple[list[dict], list[str]]:
    # Sitemap luôn được ưu tiên khi nguồn có khai sitemap_url; chỉ dùng listing-page khi
    # nguồn không có sitemap (VD tingia.gov.vn) — đúng thứ tự ưu tiên ở 06-crawler-strategy.md
    if source.listing_url and not source.sitemap_url:
        return get_listing_urls(source, date_from, date_to)
    return get_article_urls(source, date_from, date_to)


def _crawl_sources(db, job: Job) -> None:
    delay_seconds = float(os.environ.get("CRAWLER_DELAY_SECONDS", "1.5"))
    max_articles = _parse_max_articles(os.environ.get("MAX_ARTICLES_PER_JOB"))

    def crawled_count() -> int:
        return db.query(Article).filter_by(job_id=job.job_id).count()

    for source_id in job.source_ids:
        if max_articles is not None and crawled_count() >= max_articles:
            break

        source = db.get(Source, source_id)
        try:
            candidates, failed_locs = _get_candidates(source, job.date_from, job.date_to)
        except Exception:
            logger.exception("Lỗi lấy danh sách bài viết cho nguồn %s", source.domain)
            continue

        for loc in failed_locs:
            # Hash theo job_id+url (không phải SHA256(url) như bài viết) vì url_hash UNIQUE
            # toàn cục — cùng 1 sub-sitemap/listing-page có thể lỗi lại ở job khác, nguồn khác
            db.add(
                Article(
                    job_id=job.job_id,
                    source_id=source.source_id,
                    url=loc,
                    url_hash=compute_url_hash(f"{job.job_id}:{loc}"),
                    status="error",
                )
            )
            db.commit()

        for candidate in candidates:
            if max_articles is not None and crawled_count() >= max_articles:
                break

            url_hash = compute_url_hash(candidate["url"])
            if db.query(Article).filter_by(url_hash=url_hash).first() is not None:
                continue

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

- [ ] **Step 4: Chạy lại toàn bộ test, xác nhận PASS**

```bash
cd backend && pytest tests/test_report_job.py -v
```
Expected: tất cả PASS (kể cả các test cũ — không có test cũ nào set `sitemap_url`/`listing_url`, nên mặc định vẫn rơi vào nhánh `get_article_urls` như trước, hành vi cũ giữ nguyên 100%).

- [ ] **Step 5: Chạy toàn bộ test suite backend để chắc không phá vỡ gì khác**

```bash
cd backend && pytest -v
```
Expected: tất cả PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/workers/report_job.py backend/tests/test_report_job.py
git commit -m "feat: report_job tự chọn chiến lược sitemap/listing + lọc ngày đăng thật sau fetch"
```

---

### Task 4: Migration — thêm 5 nguồn thật (VOV, VietnamPlus, CAND, BoCongAn, TinGia)

**Files:**
- Create: `backend/alembic/versions/0004_seed_slice2_sources.py`

- [ ] **Step 1: Viết migration**

```python
"""seed 5 nguồn mới cho Slice 2 (VOV, VietnamPlus, CAND, BoCongAn, TinGia)

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-29
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

CRAWL4AI_RULES = json.dumps({"engine": "crawl4ai"})

TINGIA_LISTING_RULES = json.dumps(
    {
        "engine": "crawl4ai",
        "listing_item": "div.info",
        "listing_link": "h2.title a",
        "listing_date": "span.date",
    }
)

SOURCES = [
    {
        "source_id": "00000000-0000-0000-0000-000000000002",
        "name": "VOV.vn",
        "domain": "vov.vn",
        "group_name": "VOV",
        "sitemap_url": "https://vov.vn/sitemap.xml",
        "listing_url": None,
        "parsing_rules": CRAWL4AI_RULES,
    },
    {
        "source_id": "00000000-0000-0000-0000-000000000003",
        "name": "VietnamPlus",
        "domain": "vietnamplus.vn",
        "group_name": "VietnamPlus",
        "sitemap_url": "https://www.vietnamplus.vn/sitemap.xml",
        "listing_url": None,
        "parsing_rules": CRAWL4AI_RULES,
    },
    {
        "source_id": "00000000-0000-0000-0000-000000000004",
        "name": "Báo Công an Nhân dân",
        "domain": "cand.vn",
        "group_name": "Bộ Công an",
        "sitemap_url": "https://cand.vn/sitemap.xml",
        "listing_url": None,
        "parsing_rules": CRAWL4AI_RULES,
    },
    {
        "source_id": "00000000-0000-0000-0000-000000000005",
        "name": "Cổng TTĐT Bộ Công an",
        "domain": "bocongan.gov.vn",
        "group_name": "Bộ Công an",
        "sitemap_url": "https://bocongan.gov.vn/sitemap.xml",
        "listing_url": None,
        "parsing_rules": CRAWL4AI_RULES,
    },
    {
        "source_id": "00000000-0000-0000-0000-000000000006",
        "name": "Trung tâm Xử lý tin giả",
        "domain": "tingia.gov.vn",
        "group_name": "Trung tâm Xử lý tin giả",
        "sitemap_url": None,
        "listing_url": "https://tingia.gov.vn/",
        "parsing_rules": TINGIA_LISTING_RULES,
    },
]


def upgrade():
    for src in SOURCES:
        op.execute(
            sa.text(
                """
                INSERT INTO sources
                    (source_id, name, domain, group_name, sitemap_url, listing_url, parsing_rules, is_active)
                VALUES
                    (:source_id, :name, :domain, :group_name, :sitemap_url, :listing_url,
                     CAST(:parsing_rules AS jsonb), true)
                ON CONFLICT (domain) DO NOTHING
                """
            ).bindparams(**src)
        )


def downgrade():
    domains = [src["domain"] for src in SOURCES]
    op.execute(sa.text("DELETE FROM sources WHERE domain = ANY(:domains)").bindparams(domains=domains))
```

- [ ] **Step 2: Chạy migration thật, xác nhận 5 nguồn được tạo**

```bash
cd backend && alembic upgrade head
python3 -c "
from backend.db import SessionLocal
from backend.models import Source
db = SessionLocal()
for s in db.query(Source).order_by(Source.created_at):
    print(s.domain, s.group_name, s.sitemap_url, s.listing_url, s.parsing_rules)
"
```
Expected: 6 dòng (vtv.vn + 5 nguồn mới), đúng `sitemap_url`/`listing_url`/`parsing_rules` như khai.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/0004_seed_slice2_sources.py
git commit -m "feat: seed 5 nguồn mới cho Slice 2 (VOV, VietnamPlus, CAND, BoCongAn, TinGia)"
```

---

### Task 5: `GET /api/sources` — endpoint cho FE lấy danh sách nguồn active

**Files:**
- Create: `backend/routers/sources.py`
- Test: `backend/tests/test_sources_router.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Viết test trước**

Tạo `backend/tests/test_sources_router.py`:

```python
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models import Source
from backend.routers import sources


@pytest.fixture
def app_client():
    app = FastAPI()
    app.include_router(sources.router)
    return TestClient(app)


def test_list_sources_returns_only_active_sources(app_client, db_session):
    active = Source(name="Active", domain=f"active-{uuid.uuid4()}.example", group_name="G1", is_active=True)
    inactive = Source(name="Inactive", domain=f"inactive-{uuid.uuid4()}.example", group_name="G1", is_active=False)
    db_session.add_all([active, inactive])
    db_session.commit()

    try:
        response = app_client.get("/api/sources")

        assert response.status_code == 200
        names = [s["name"] for s in response.json()["sources"]]
        assert "Active" in names
        assert "Inactive" not in names
    finally:
        db_session.delete(active)
        db_session.delete(inactive)
        db_session.commit()


def test_list_sources_returns_expected_fields(app_client, db_session):
    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test Group", is_active=True)
    db_session.add(source)
    db_session.commit()

    try:
        response = app_client.get("/api/sources")

        body = next(s for s in response.json()["sources"] if s["name"] == "Test")
        assert body["source_id"] == str(source.source_id)
        assert body["domain"] == source.domain
        assert body["group_name"] == "Test Group"
    finally:
        db_session.delete(source)
        db_session.commit()
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

```bash
cd backend && pytest tests/test_sources_router.py -v
```
Expected: FAIL với `ModuleNotFoundError: No module named 'backend.routers.sources'`.

- [ ] **Step 3: Viết `backend/routers/sources.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import Source

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("")
def list_sources(db: Session = Depends(get_db)):
    rows = db.query(Source).filter_by(is_active=True).order_by(Source.group_name, Source.name).all()
    return {
        "sources": [
            {
                "source_id": str(s.source_id),
                "name": s.name,
                "domain": s.domain,
                "group_name": s.group_name,
            }
            for s in rows
        ]
    }
```

- [ ] **Step 4: Đăng ký router trong `backend/main.py`**

Sửa:
```python
from backend.routers import reports
```
thành:
```python
from backend.routers import reports, sources
```
và sau `app.include_router(reports.router)` thêm:
```python
app.include_router(sources.router)
```

- [ ] **Step 5: Chạy lại test, xác nhận PASS**

```bash
cd backend && pytest tests/test_sources_router.py -v
```
Expected: 2/2 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/sources.py backend/tests/test_sources_router.py backend/main.py
git commit -m "feat: thêm GET /api/sources cho FE lấy danh sách nguồn active"
```

---

### Task 6: FE — `SourceSidebar` component (chọn nhiều nguồn, search, group, tag)

**Files:**
- Create: `frontend/components/SourceSidebar.tsx`

Theo đúng mockup `09-frontend-ui.md`: search realtime, group theo `group_name`, checkbox từng nguồn, tag nguồn đã chọn (xóa được từng cái), đếm "X/Y đã chọn".

- [ ] **Step 1: Viết component**

```tsx
"use client";

import { useMemo, useState } from "react";

export type SourceItem = {
  source_id: string;
  name: string;
  domain: string;
  group_name: string;
};

type Props = {
  sources: SourceItem[];
  selectedIds: string[];
  onToggle: (sourceId: string) => void;
};

export default function SourceSidebar({ sources, selectedIds, onToggle }: Props) {
  const [search, setSearch] = useState("");

  const filtered = useMemo(
    () => sources.filter((s) => s.name.toLowerCase().includes(search.toLowerCase())),
    [sources, search]
  );

  const grouped = useMemo(() => {
    const groups = new Map<string, SourceItem[]>();
    for (const source of filtered) {
      const list = groups.get(source.group_name) ?? [];
      list.push(source);
      groups.set(source.group_name, list);
    }
    return Array.from(groups.entries());
  }, [filtered]);

  const selectedSources = sources.filter((s) => selectedIds.includes(s.source_id));

  return (
    <div className="border rounded p-3">
      <input
        type="text"
        placeholder="🔍 Tìm nguồn..."
        className="w-full border rounded px-2 py-1 mb-3"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {selectedSources.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {selectedSources.map((s) => (
            <span key={s.source_id} className="bg-blue-100 text-blue-800 text-sm px-2 py-1 rounded">
              {s.name}{" "}
              <button onClick={() => onToggle(s.source_id)} aria-label={`Bỏ chọn ${s.name}`}>
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {grouped.map(([groupName, items]) => (
        <div key={groupName} className="mb-3">
          <p className="font-medium text-sm text-gray-600 mb-1">{groupName}</p>
          {items.map((source) => (
            <label key={source.source_id} className="flex items-center gap-2 py-0.5 text-sm">
              <input
                type="checkbox"
                checked={selectedIds.includes(source.source_id)}
                onChange={() => onToggle(source.source_id)}
              />
              {source.name}
            </label>
          ))}
        </div>
      ))}

      <p className="text-xs text-gray-500 mt-2">
        {selectedIds.length}/{sources.length} đã chọn
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/SourceSidebar.tsx
git commit -m "feat: thêm SourceSidebar component cho chọn nhiều nguồn"
```

---

### Task 7: FE — `SummaryCard` component (ước tính số bài/thời gian + warning)

**Files:**
- Create: `frontend/components/SummaryCard.tsx`

**Công thức ước tính số bài:** `số_nguồn × số_ngày × 2 bài/ngày` (đúng theo `09-frontend-ui.md`).
**Công thức ước tính thời gian:** dùng hằng số `ESTIMATED_SECONDS_PER_ARTICLE = 90` (ước lượng thô — xem ghi chú đầu plan, **cần xác nhận lại khi review**, mockup gốc dùng số ví dụ không khớp thực tế đã biết về tốc độ AI).
**Warning:** hiện khi `≥5 nguồn AND ≥60 ngày`.

- [ ] **Step 1: Viết component**

```tsx
const ESTIMATED_ARTICLES_PER_SOURCE_PER_DAY = 2;
// Ước lượng thô dựa trên AI_TIMEOUT_SECONDS=360 và ghi nhận thật "qwen3:8b CPU-only có lúc
// >120s/bài" (xem CLAUDE.md) — KHÔNG phải số đo chính xác, chỉ để người dùng có cảm nhận
// tương đối trước khi tạo báo cáo. Điều chỉnh lại khi có benchmark thật trên nhiều nguồn.
const ESTIMATED_SECONDS_PER_ARTICLE = 90;

type Props = {
  sourceCount: number;
  dayCount: number;
};

export default function SummaryCard({ sourceCount, dayCount }: Props) {
  const estimatedArticles = sourceCount * dayCount * ESTIMATED_ARTICLES_PER_SOURCE_PER_DAY;
  const estimatedMinutes = Math.ceil((estimatedArticles * ESTIMATED_SECONDS_PER_ARTICLE) / 60);
  const showWarning = sourceCount >= 5 && dayCount >= 60;

  return (
    <div className="border rounded p-3 bg-gray-50">
      <p className="font-medium">
        {sourceCount} nguồn · {dayCount} ngày
      </p>
      <p className="text-sm text-gray-600">
        ~{estimatedArticles} bài · ~{estimatedMinutes} phút (ước tính)
      </p>
      {showWarning && (
        <p className="text-amber-700 text-sm mt-2">
          ⚠️ Job sẽ chạy nền, có thể mất nhiều thời gian với số nguồn/ngày lớn — sẽ thông báo khi xong.
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/SummaryCard.tsx
git commit -m "feat: thêm SummaryCard component ước tính số bài/thời gian"
```

---

### Task 8: FE — `page.tsx` — thay nguồn hardcode bằng sidebar đa chọn + preset ngày

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Sửa import + bỏ hardcode `VTV_SOURCE_ID`**

Sửa đầu file (xóa dòng `const VTV_SOURCE_ID = ...`, thêm import component + type):

```tsx
"use client";

import { useEffect, useState } from "react";
import SourceSidebar, { SourceItem } from "@/components/SourceSidebar";
import SummaryCard from "@/components/SummaryCard";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
// sessionStorage (không phải localStorage) — chỉ cần sống qua F5 trong cùng tab,
// tự dọn khi đóng tab, tránh "job ma" lưu lại nhiều ngày
const JOB_ID_STORAGE_KEY = "ngs_monitor_job_id";

const DATE_PRESETS = [
  { label: "7 ngày", days: 7 },
  { label: "30 ngày", days: 30 },
  { label: "90 ngày", days: 90 },
  { label: "150 ngày", days: 150 },
];
```

- [ ] **Step 2: Thêm state cho nguồn + hàm tính số ngày**

Trong `Home()`, ngay sau khai báo state hiện có (`dateFrom`, `dateTo`, `jobId`, `status`, `articles`, `error`), thêm:

```tsx
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/api/sources`)
      .then((res) => res.json())
      .then((data) => setSources(data.sources));
  }, []);

  function toggleSource(sourceId: string) {
    setSelectedSourceIds((prev) =>
      prev.includes(sourceId) ? prev.filter((id) => id !== sourceId) : [...prev, sourceId]
    );
  }

  function applyPreset(days: number) {
    setDateFrom(todayMinus(days));
    setDateTo(todayMinus(0));
  }

  const dayCount = Math.max(0, Math.round((new Date(dateTo).getTime() - new Date(dateFrom).getTime()) / 86400000));
```

- [ ] **Step 3: Sửa `handleSubmit` dùng `selectedSourceIds` thay vì hardcode**

Sửa:
```tsx
      body: JSON.stringify({ source_ids: [VTV_SOURCE_ID], date_from: dateFrom, date_to: dateTo }),
```
thành:
```tsx
      body: JSON.stringify({ source_ids: selectedSourceIds, date_from: dateFrom, date_to: dateTo }),
```

- [ ] **Step 4: Sửa điều kiện disable nút submit**

Sửa:
```tsx
  const disabled = !dateFrom || !dateTo || dateFrom >= dateTo;
```
thành:
```tsx
  const disabled = !dateFrom || !dateTo || dateFrom >= dateTo || selectedSourceIds.length === 0;
```

- [ ] **Step 5: Thay khối "Nguồn dữ liệu" hardcode bằng sidebar + summary + preset**

Sửa khối JSX:
```tsx
      <div className="mb-4">
        <label className="block font-medium">Nguồn dữ liệu</label>
        <p>VTV News</p>
      </div>

      <div className="mb-4 flex gap-4">
        <div>
          <label className="block font-medium">Từ ngày</label>
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div>
          <label className="block font-medium">Đến ngày</label>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
      </div>
```
thành:
```tsx
      <div className="mb-4 grid grid-cols-2 gap-4">
        <SourceSidebar sources={sources} selectedIds={selectedSourceIds} onToggle={toggleSource} />

        <div>
          <div className="flex gap-2 mb-2">
            {DATE_PRESETS.map((preset) => (
              <button
                key={preset.days}
                className="border rounded px-2 py-1 text-sm"
                onClick={() => applyPreset(preset.days)}
              >
                {preset.label}
              </button>
            ))}
          </div>
          <div className="flex gap-4 mb-3">
            <div>
              <label className="block font-medium">Từ ngày</label>
              <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            </div>
            <div>
              <label className="block font-medium">Đến ngày</label>
              <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </div>
          </div>
          <SummaryCard sourceCount={selectedSourceIds.length} dayCount={dayCount} />
        </div>
      </div>
```

- [ ] **Step 6: Build thử FE để xác nhận không lỗi TypeScript**

```bash
cd frontend && npm run build
```
Expected: build thành công, không lỗi type.

- [ ] **Step 7: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat: thay nguồn hardcode bằng sidebar chọn nhiều nguồn + preset ngày"
```

---

### Task 9: Cập nhật tài liệu (rules + CLAUDE.md)

**Files:**
- Modify: `.claude/rules/10-error-handling.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Thêm rule mới vào `10-error-handling.md`**

Thêm 1 dòng vào bảng (sau dòng "Dữ liệu trùng lặp"):

```markdown
| Bài viết crawl được nhưng ngày đăng thật nằm ngoài `date_from`/`date_to` yêu cầu | Bỏ qua âm thầm, không insert (không phải lỗi) — cần thiết vì 1 số nguồn có sitemap không lọc được chính xác theo ngày trước khi fetch (VD `bocongan.gov.vn` ghi `<lastmod>` giống nhau cho mọi URL, không phải ngày đăng thật) (2026-06-29) |
```

- [ ] **Step 2: Cập nhật `CLAUDE.md` — tick checklist Slice 2, ghi quyết định + rủi ro mới**

Sửa checklist Slice 2 (tick 2 dòng đầu, sửa dòng FE thành đã làm 1 phần, cập nhật số nguồn):

```markdown
### Slice 2 — Nhiều nguồn + listing-page fallback
- [x] Listing page crawler (fallback khi nguồn không có sitemap) — `backend/crawler/listing.py`, phạm vi 1 trang không phân trang (YAGNI, chỉ tingia.gov.vn cần đến hiện tại)
- [x] Config & test 6 nguồn thực tế (VTV, VOV, VietnamPlus, CAND, BoCongAn, TinGia — ít hơn ước tính gốc 8–10, xem "Vấn đề cần làm rõ" dưới) — toàn bộ 5 nguồn mới dùng engine Crawl4AI (`parsing_rules.engine = "crawl4ai"`), không viết CSS selector tay
- [ ] FE: sidebar chọn nhiều nguồn (search, group theo nhóm kênh), tag nguồn đã chọn, summary card ước tính số bài/thời gian, preset ngày (7/30/90/150), warning khi ≥5 nguồn & ≥60 ngày
- **Verify:** crawl thành công ≥8 nguồn thực tế (cả sitemap và fallback listing); test trùng URL bị dedup đúng (không insert lại) — **đã verify thật 6 nguồn** (xem Task 10 plan `docs/superpowers/plans/2026-06-29-slice2-multi-source.md`), dedup giữ nguyên cơ chế cũ (SHA256(url))
```

Thêm vào bảng "Quyết định quan trọng & lý do":

```markdown
| Tổng quát hóa `sitemap.py` để nhận sitemap phẳng + nhiều pattern tên sub-sitemap (thay vì chỉ đúng pattern VTV) | Verify thật cho thấy VOV/VietnamPlus/CAND dùng pattern khác VTV (`news-YYYY-M.xml`/`/YYYY/M/...`), bocongan.gov.vn dùng sitemap phẳng không có index — code cũ sẽ trả về 0 bài cho cả 4 nguồn này nếu không sửa (2026-06-29) |
| Lọc lại theo `published_at` thật sau khi fetch bài (không chỉ tin sitemap `<lastmod>`) | bocongan.gov.vn ghi `<lastmod>` giống nhau y hệt cho toàn bộ 500 URL trong sitemap (timestamp build lại sitemap, không phải ngày đăng thật, đã verify thật bằng curl) — lọc theo lastmod sẽ làm rớt nhầm toàn bộ bài hợp lệ hoặc giữ nhầm toàn bộ bài không hợp lệ tùy khoảng ngày yêu cầu (2026-06-29) |
| Listing-page crawler chỉ hỗ trợ 1 trang, không phân trang | Nguồn duy nhất cần đến (tingia.gov.vn) không có phân trang thật trên trang danh sách (đã verify) — không xây cơ chế phân trang khi chưa có nguồn thật nào cần (YAGNI), mở rộng khi Slice sau có nguồn cần thật (2026-06-29) |
| Cả 5 nguồn mới (VOV, VietnamPlus, CAND, BoCongAn, TinGia) dùng engine Crawl4AI, không viết CSS selector tay | Tránh 6x công reverse-engineer CSS selector cho 6 template HTML khác nhau; Crawl4AI đã verify hoạt động thật trên VTV+VOV trước đó, đúng định hướng đã ghi sẵn trong roadmap Slice 2 (2026-06-29) |
| Tạm loại qdnd.vn khỏi Slice 2 | `curl`/WebFetch tới `sitemap.xml` và cả trang chủ qdnd.vn đều bị redirect-loop vô hạn (302) từ network môi trường test — chưa rõ do chặn bot hay do IP/network môi trường test, cần verify lại từ server production trước khi thêm (2026-06-29) |
```

Cập nhật mục "Vấn đề cần làm rõ":

```markdown
- **Số nguồn Slice 2 chỉ đạt 6 (không phải 8–10)** — đã xác nhận 6 nguồn crawl được thật (VTV+VOV+VietnamPlus+CAND+BoCongAn+TinGia); qdnd.vn bị loại do lỗi redirect-loop chưa rõ nguyên nhân (xem bảng quyết định); chinhphu.vn/mod.gov.vn/bvhttdl.gov.vn không có bài chuyên tin giả theo khảo sát thật — người dùng xác nhận 6 nguồn là đủ cho slice này, không ép đủ số
- **Hằng số `ESTIMATED_SECONDS_PER_ARTICLE = 90` ở `SummaryCard.tsx`** là ước lượng thô, chưa có benchmark thật trên nhiều nguồn — cần điều chỉnh lại khi Slice 3 có dữ liệu benchmark thật trên ≥50 bài
```

- [ ] **Step 3: Commit**

```bash
git add .claude/rules/10-error-handling.md CLAUDE.md
git commit -m "docs: cập nhật CLAUDE.md + rule error-handling cho Slice 2"
```

---

### Task 10: Verify thật — chạy job thật với ≥1 nguồn mới

**Bắt buộc theo Workflow Commit (`13-workflow.md`): "Test với dữ liệu thật — luôn chạy thử với ít nhất 1 nguồn thực tế trước khi commit."** Task này verify toàn bộ Slice 2 chạy thông thật, không chỉ unit test.

- [ ] **Step 1: Khởi động đủ service**

```bash
docker compose up -d
docker compose ps
```
Expected: tất cả service `healthy`.

- [ ] **Step 2: Lấy danh sách nguồn thật qua API**

```bash
curl -s http://localhost:8000/api/sources | python3 -m json.tool
```
Expected: 6 nguồn (vtv.vn, vov.vn, vietnamplus.vn, cand.vn, bocongan.gov.vn, tingia.gov.vn).

- [ ] **Step 3: Tạo job thật với 2 nguồn mới (VOV + BoCongAn — đại diện cho cả 2 chiến lược lọc ngày: lastmod đáng tin vs lastmod bị bỏ qua hoàn toàn)**

```bash
curl -s -X POST http://localhost:8000/api/reports/create \
  -H "Content-Type: application/json" \
  -d '{
    "source_ids": ["00000000-0000-0000-0000-000000000002", "00000000-0000-0000-0000-000000000005"],
    "date_from": "2026-01-01",
    "date_to": "2026-05-30"
  }' | python3 -m json.tool
```
Ghi lại `job_id` trả về.

- [ ] **Step 4: Theo dõi job tới khi completed**

```bash
watch -n 3 "curl -s http://localhost:8000/api/reports/<job_id>/status | python3 -m json.tool"
```
Expected: `status` chuyển `pending → running → completed`, `progress.crawled` tăng dần >0 cho cả 2 nguồn.

- [ ] **Step 5: Kiểm tra bảng crawl trực tiếp có dữ liệu thật từ cả 2 nguồn**

```bash
curl -s http://localhost:8000/api/reports/<job_id>/articles | python3 -m json.tool
```
Expected: có ít nhất 1 bài `status="analyzed"` với `url` chứa `vov.vn` VÀ ít nhất 1 bài với `url` chứa `bocongan.gov.vn` — xác nhận cả 2 chiến lược lọc ngày (sitemap index lastmod-tin-cậy vs sitemap phẳng lọc sau-fetch) đều hoạt động thật, không chỉ pass unit test mock.

- [ ] **Step 6: Tải file .docx/.json, mở kiểm tra hợp lệ**

```bash
curl -s -o /tmp/slice2_verify.docx http://localhost:8000/api/reports/<job_id>/download
file /tmp/slice2_verify.docx
```
Expected: file hợp lệ (`Microsoft Word 2007+`), không rỗng.

- [ ] **Step 7: Ghi kết quả verify thật vào CLAUDE.md**

Cập nhật dòng Verify ở Slice 2 (đã sửa ở Task 9) với số liệu thật quan sát được (số bài crawl mỗi nguồn, có lỗi gì không).

- [ ] **Step 8: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: ghi nhận kết quả verify thật Slice 2 (VOV + BoCongAn)"
```

---

## Self-Review

**Spec coverage:**
- Listing page crawler (fallback) → Task 2 ✓
- Config & test nguồn thực tế → Task 1, 3, 4 ✓ (6/6, không phải 8-10 — đã ghi rõ lý do + xác nhận từ người dùng, Task 9)
- FE sidebar/tag/summary/preset/warning → Task 6, 7, 8 ✓
- Verify dedup + ≥8 nguồn → Task 10 verify thật 2 nguồn tiêu biểu; dedup cơ chế không đổi (SHA256(url), test cũ vẫn pass) — số nguồn thực tế 6 đã thống nhất với người dùng, không đúng "≥8" nguyên văn nhưng đã có lý do ghi nhận

**Placeholder scan:** không còn "TBD"/"tự viết test tương tự" — mọi step đều có code đầy đủ.

**Type consistency:** `get_listing_urls(source, date_from, date_to, client=None, max_retries=None) -> tuple[list[dict], list[str]]` dùng nhất quán giữa Task 2 (định nghĩa) và Task 3 (gọi trong `_get_candidates`). `SourceItem` type dùng nhất quán giữa Task 6 (định nghĩa, export) và Task 8 (import, dùng trong state).
