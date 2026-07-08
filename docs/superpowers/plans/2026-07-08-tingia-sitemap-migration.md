# TinGia chuyển sang crawl bằng sitemap (curated sub-sitemap list) thay listing-page

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development khi code — viết test FAIL trước, code sau. Steps dùng checkbox (`- [ ]`) để track.

**Goal:** tingia.gov.vn thật ra CÓ sitemap XML (`https://tingia.gov.vn/sitemap.xml`), nhưng đã verify thật (curl 2026-07-08) cấu trúc khác các nguồn dùng sitemap hiện có: top-level là `<urlset>` phẳng (không phải `<sitemapindex>`) trộn lẫn 18 sub-sitemap `.xml` (chia theo CHỦ ĐỀ/tag, không theo ngày) + 3 trang tĩnh, và mọi `<lastmod>` ở top-level bị đóng băng cùng 1 timestamp build (giống vấn đề đã gặp ở bocongan.gov.vn). Vì vậy không dùng được cơ chế index-based hiện có (`_SITEMAP_DATE_PATTERNS`) — chuyển sang danh sách 5 sub-sitemap được chọn thủ công (`tin-vua-check`, `multimedia`, `cong-bo-tin-gia`, `vaccine-phong-chong-tin-gia`, `linh-vuc`), lưu trong `parsing_rules.sitemap_pages` (JSONB, sửa được qua migration/DB — không hardcode trong `sitemap.py`). Do sub-sitemap chia theo tag, 1 bài có thể xuất hiện ở nhiều sub-sitemap → cần dedup URL trước khi trả về danh sách candidate (tránh crawl trùng 1 bài 2 lần).

Đồng thời xóa cấu hình listing-page cũ của TinGia (nguồn duy nhất từng dùng nhánh 1-trang của `listing.py`) — **giữ nguyên cơ chế `listing.py`** (đã xác nhận với user: đây là fallback tổng quát theo 06-crawler-strategy.md, không phải code riêng của TinGia, có thể cần lại cho nguồn tương lai không có sitemap).

**Architecture:**
- Field mới `parsing_rules.sitemap_pages: list[str]` — danh sách đầy đủ URL sub-sitemap cần fetch (không có tầng "declared vs fetch subset" như `listing_pages`/`fetch_pages` của BoCongAn — TinGia chỉ cần 1 list duy nhất, sửa trực tiếp là điều chỉnh được ngay, đúng yêu cầu "linh hoạt thêm/sửa/xóa" của user).
- `get_article_urls()` (`sitemap.py`): thêm nhánh sớm nhất trong hàm — nếu `source.parsing_rules.get("sitemap_pages")` có giá trị → gọi thẳng `_fetch_declared_sitemap_pages()`, **không đụng tới `source.sitemap_url`** (TinGia sẽ có `sitemap_url=NULL` sau migration).
- `_fetch_declared_sitemap_pages()`: fetch tuần tự từng URL trong `sitemap_pages` (delay + retry dùng lại `_fetch_with_retry` sẵn có), lọc theo `<lastmod>` thật bên trong từng sub-sitemap (dùng lại `_extract_urls_in_range`), dedup bằng `set` URL đã thấy — bài trùng ở sub-sitemap sau bị bỏ qua, không fetch lại (fetch ở đây là fetch sub-sitemap XML, không phải fetch bài — dedup URL tránh việc bước sau (`report_job.py`) phải gọi `fetch_article_dispatch()` 2 lần cho cùng 1 bài).
- **`_get_candidates()` (`report_job.py`) — KHÔNG cần sửa.** Đã verify: với TinGia sau migration (`listing_pages` không có, `listing_url=NULL`), 2 nhánh listing hiện tại đều không khớp → tự động rơi vào `return get_article_urls(...)`, đúng ý muốn. (Sửa lại so với giải thích ban đầu trong hội thoại — lúc đầu tưởng cần thêm nhánh riêng, kiểm tra kỹ lại thì không cần.)
- Migration mới `0006`: cập nhật (UPDATE, không sửa `0004` cũ) `sources` row của `tingia.gov.vn`: `sitemap_url=NULL`, `listing_url=NULL`, `parsing_rules` đổi từ `TINGIA_LISTING_RULES` (listing_item/listing_link/listing_date) sang `{"engine": "crawl4ai", "sitemap_pages": [...]}`.

**Tech Stack:** Python, pytest, httpx.MockTransport, Alembic

---

## Mapping file → trách nhiệm sau khi sửa

| File | Thay đổi |
|---|---|
| `backend/crawler/sitemap.py` | Thêm `_fetch_declared_sitemap_pages()`; thêm nhánh early-return trong `get_article_urls()` khi `parsing_rules.sitemap_pages` có giá trị |
| `backend/tests/test_sitemap.py` | Thêm 4 test mới cho nhánh `sitemap_pages` |
| `backend/tests/test_report_job.py` | Thêm 1 test xác nhận routing (không sửa `report_job.py`) |
| `backend/alembic/versions/0006_tingia_sitemap_pages.py` | Migration mới — UPDATE row TinGia, downgrade khôi phục cấu hình `0004` |
| `CLAUDE.md` | Ghi quyết định mới, cập nhật trạng thái TinGia, đóng gap "chưa verify job thật" đã flag trước đó (nếu verify thật thành công ở Task 6) |

> **Không sửa `listing.py`, không sửa `_get_candidates()` trong `report_job.py`** — đã xác nhận cả 2 không cần đổi.

---

## Task 1 — Viết failing tests cho `get_article_urls` xử lý `parsing_rules.sitemap_pages`

**Files:**
- Modify: `backend/tests/test_sitemap.py`

- [ ] **Step 1.1: Thêm `TinGiaSource` class**

```python
class TinGiaSource:
    """sitemap_url=None cố ý — nếu code lỡ đọc source.sitemap_url sẽ crash ngay, phát hiện sớm bug routing."""
    sitemap_url = None
    domain = "tingia.gov.vn"
    parsing_rules = {
        "sitemap_pages": [
            "https://tingia.gov.vn/sitemap/tin-vua-check.xml",
            "https://tingia.gov.vn/sitemap/multimedia.xml",
        ]
    }
```

- [ ] **Step 1.2: Test chỉ fetch đúng URL đã khai, không đụng index**

```python
def test_sitemap_pages_fetches_only_declared_urls_without_touching_index():
    sub_a = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://tingia.gov.vn/bai-a</loc><lastmod>2026-06-15T00:00:00+07:00</lastmod></url>
</urlset>"""
    sub_b = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://tingia.gov.vn/bai-b</loc><lastmod>2026-06-16T00:00:00+07:00</lastmod></url>
</urlset>"""
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if "tin-vua-check" in str(request.url):
            return httpx.Response(200, text=sub_a)
        if "multimedia" in str(request.url):
            return httpx.Response(200, text=sub_b)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        TinGiaSource(), date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
        client=client, delay_seconds=0,
    )

    assert sorted(item["url"] for item in result) == ["https://tingia.gov.vn/bai-a", "https://tingia.gov.vn/bai-b"]
    assert all("sitemap.xml" not in url or "sitemap/" in url for url in requested)  # không gọi index /sitemap.xml
    assert failed_locs == []
```

- [ ] **Step 1.3: Test dedup URL trùng giữa 2 sub-sitemap**

```python
def test_sitemap_pages_dedups_url_appearing_in_multiple_declared_sub_sitemaps():
    same_article = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://tingia.gov.vn/bai-trung</loc><lastmod>2026-06-15T00:00:00+07:00</lastmod></url>
</urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=same_article)  # cả 2 sub-sitemap trả về cùng 1 URL

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        TinGiaSource(), date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
        client=client, delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://tingia.gov.vn/bai-trung"]  # chỉ 1, không lặp
    assert failed_locs == []
```

- [ ] **Step 1.4: Test vẫn lọc theo `<lastmod>` thật trong khoảng ngày yêu cầu**

```python
def test_sitemap_pages_still_filters_by_lastmod_date_range():
    mixed = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://tingia.gov.vn/bai-trong-khoang</loc><lastmod>2026-06-15T00:00:00+07:00</lastmod></url>
    <url><loc>https://tingia.gov.vn/bai-ngoai-khoang</loc><lastmod>2025-01-01T00:00:00+07:00</lastmod></url>
</urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=mixed)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        TinGiaSource(), date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
        client=client, delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://tingia.gov.vn/bai-trong-khoang"]
```

- [ ] **Step 1.5: Test 1 sub-sitemap lỗi hết retry → ghi nhận `failed_locs`, sub-sitemap khác vẫn xử lý**

```python
def test_sitemap_pages_records_failed_loc_for_one_failing_sub_sitemap_others_still_processed():
    ok_sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://tingia.gov.vn/bai-ok</loc><lastmod>2026-06-15T00:00:00+07:00</lastmod></url>
</urlset>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if "tin-vua-check" in str(request.url):
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, text=ok_sitemap)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        TinGiaSource(), date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
        client=client, delay_seconds=0, max_retries=1,
    )

    assert [item["url"] for item in result] == ["https://tingia.gov.vn/bai-ok"]
    assert failed_locs == ["https://tingia.gov.vn/sitemap/tin-vua-check.xml"]
```

- [ ] **Step 1.6: Chạy để xác nhận FAIL (expected — `get_article_urls` chưa đọc `parsing_rules`)**

```bash
docker compose exec backend pytest backend/tests/test_sitemap.py -k sitemap_pages -v
```

Expected: 4 FAILED (hàm hiện tại crash vì `source.sitemap_url=None` bị gọi `client.get(None)`, hoặc `AttributeError`/lỗi mock request không khớp).

---

## Task 2 — Implement `_fetch_declared_sitemap_pages` + wire vào `get_article_urls`

**Files:**
- Modify: `backend/crawler/sitemap.py`

- [ ] **Step 2.1: Thêm hàm mới, đặt trước `get_article_urls`**

```python
def _fetch_declared_sitemap_pages(
    sitemap_pages: list[str],
    date_from: date,
    date_to: date,
    client: httpx.Client,
    delay_seconds: float,
    max_retries: int,
) -> tuple[list[dict], list[str]]:
    # Sub-sitemap chia theo CHỦ ĐỀ (VD tingia.gov.vn) — 1 bài có thể nằm ở nhiều sub-sitemap,
    # dedup theo URL để không trả về trùng (tránh report_job.py fetch cùng 1 bài 2 lần).
    seen: set[str] = set()
    results: list[dict] = []
    failed: list[str] = []
    for loc in sitemap_pages:
        time.sleep(delay_seconds)
        resp = _fetch_with_retry(client, loc, max_retries)
        if resp is None:
            failed.append(loc)
            continue
        soup = BeautifulSoup(resp.text, "xml")
        for item in _extract_urls_in_range(soup, date_from, date_to):
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            results.append(item)
    return results, failed
```

- [ ] **Step 2.2: Thêm nhánh early-return trong `get_article_urls`, ngay sau dòng khởi tạo `max_retries`**

Tìm đoạn:
```python
    if max_retries is None:
        max_retries = int(os.environ.get("CRAWLER_MAX_RETRIES", "3"))

    try:
        index_resp = client.get(source.sitemap_url)
```

Thay bằng:
```python
    if max_retries is None:
        max_retries = int(os.environ.get("CRAWLER_MAX_RETRIES", "3"))

    sitemap_pages = source.parsing_rules.get("sitemap_pages")
    if sitemap_pages:
        # Danh sách sub-sitemap curated thủ công (VD tingia.gov.vn — top-level sitemap.xml
        # là urlset phẳng trộn lẫn trang tĩnh + sub-sitemap chia theo tag, lastmod đóng băng ở
        # top-level, không dùng được cơ chế index/_SITEMAP_DATE_PATTERNS hiện có). Không đụng
        # source.sitemap_url — nguồn dùng nhánh này luôn có sitemap_url=NULL.
        try:
            return _fetch_declared_sitemap_pages(
                sitemap_pages, date_from, date_to, client, delay_seconds, max_retries
            )
        finally:
            if owns_client:
                client.close()

    try:
        index_resp = client.get(source.sitemap_url)
```

- [ ] **Step 2.3: Chạy lại test Task 1 — phải PASS**

```bash
docker compose exec backend pytest backend/tests/test_sitemap.py -k sitemap_pages -v
```

- [ ] **Step 2.4: Chạy toàn bộ `test_sitemap.py` — không được regression**

```bash
docker compose exec backend pytest backend/tests/test_sitemap.py -v
```

---

## Task 3 — Test xác nhận routing ở `report_job.py` không cần sửa

**Files:**
- Modify: `backend/tests/test_report_job.py`

- [ ] **Step 3.1: Thêm test xác nhận nguồn có `sitemap_pages` route qua `get_article_urls`, không qua `get_listing_urls`**

Đặt cạnh `test_crawl_sources_prefers_listing_pages_over_sitemap_when_both_configured` (theo đúng pattern `patch(...)` đã có trong file):

```python
def test_crawl_sources_routes_sitemap_pages_source_through_get_article_urls(db_session, monkeypatch):
    source = Source(
        name="Test",
        domain=f"test-{uuid.uuid4()}.example",
        group_name="Test",
        sitemap_url=None,
        listing_url=None,
        parsing_rules={"sitemap_pages": ["https://example.test/sitemap/a.xml"]},
    )
    # ... (giữ nguyên phần setup job/monkeypatch giống 2 test routing hiện có ở trên nó)
    with patch("backend.workers.report_job.get_article_urls", return_value=([], [])) as mock_sitemap, patch(
        "backend.workers.report_job.get_listing_urls"
    ) as mock_listing:
        # gọi _crawl_sources như 2 test routing hiện có
        ...
        mock_sitemap.assert_called_once()
        mock_listing.assert_not_called()
```

> Viết đúng theo khung setup (tạo `job`, `db_session.add`, gọi `_crawl_sources`) đang dùng ở 2 test routing liền kề — copy cấu trúc, chỉ đổi `parsing_rules`/assertion.

- [ ] **Step 3.2: Chạy test mới — phải PASS ngay (không cần sửa `report_job.py`)**

```bash
docker compose exec backend pytest backend/tests/test_report_job.py -k sitemap_pages -v
```

Nếu FAIL → nghĩa là giả định "không cần sửa `_get_candidates()`" sai, cần quay lại thêm nhánh tường minh cho `sitemap_pages` trong `_get_candidates()` giống nhánh `listing_pages`.

---

## Task 4 — Migration `0006`: cập nhật DB TinGia sang sitemap_pages

**Files:**
- Create: `backend/alembic/versions/0006_tingia_sitemap_pages.py`

- [ ] **Step 4.1: Viết migration theo đúng khuôn mẫu `0005`**

```python
"""tingia.gov.vn: chuyển từ listing-page sang sitemap curated (sitemap_pages)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-08
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

OLD_PARSING_RULES = json.dumps(
    {
        "engine": "crawl4ai",
        "listing_item": "div.info",
        "listing_link": "h2.title a",
        "listing_date": "span.date",
    }
)
OLD_LISTING_URL = "https://tingia.gov.vn/"

NEW_PARSING_RULES = json.dumps(
    {
        "engine": "crawl4ai",
        "sitemap_pages": [
            "https://tingia.gov.vn/sitemap/tin-vua-check.xml",
            "https://tingia.gov.vn/sitemap/multimedia.xml",
            "https://tingia.gov.vn/sitemap/cong-bo-tin-gia.xml",
            "https://tingia.gov.vn/sitemap/vaccine-phong-chong-tin-gia.xml",
            "https://tingia.gov.vn/sitemap/linh-vuc.xml",
        ],
    }
)


def upgrade():
    op.execute(
        sa.text(
            """
            UPDATE sources
            SET parsing_rules = CAST(:parsing_rules AS jsonb), sitemap_url = NULL, listing_url = NULL
            WHERE domain = 'tingia.gov.vn'
            """
        ).bindparams(parsing_rules=NEW_PARSING_RULES)
    )


def downgrade():
    op.execute(
        sa.text(
            """
            UPDATE sources
            SET parsing_rules = CAST(:parsing_rules AS jsonb), sitemap_url = NULL, listing_url = :listing_url
            WHERE domain = 'tingia.gov.vn'
            """
        ).bindparams(parsing_rules=OLD_PARSING_RULES, listing_url=OLD_LISTING_URL)
    )
```

- [ ] **Step 4.2: Chạy migration thật trên DB dev**

```bash
docker compose exec backend alembic upgrade head
```

- [ ] **Step 4.3: Verify DB đã đổi đúng**

```bash
docker compose exec db psql -U <user> -d ngs_monitor -c "SELECT domain, sitemap_url, listing_url, parsing_rules FROM sources WHERE domain = 'tingia.gov.vn';"
```

Expected: `sitemap_url=NULL`, `listing_url=NULL`, `parsing_rules` có `sitemap_pages` với 5 URL.

---

## Task 5 — Verify thật với dữ liệu thật (bắt buộc trước khi commit theo CLAUDE.md)

- [ ] **Step 5.1: Chạy job thật chỉ với source TinGia**

Gọi `POST /api/reports/create` với `source_ids=[<tingia source_id>]`, date range đủ rộng để chắc chắn có bài (VD 90 ngày gần nhất) — tingia.gov.vn không bị chặn WAF (đã confirm bằng curl trong hội thoại này, khác bocongan.gov.vn).

- [ ] **Step 5.2: Poll `GET /api/reports/{job_id}/status` tới khi `completed`, kiểm tra:**
  - Có ít nhất 1 bài `status="analyzed"` từ đúng 5 sub-sitemap đã khai (không có bài nào từ sub-sitemap ngoài danh sách)
  - Không có URL trùng lặp trong `GET /api/reports/{job_id}/articles`
  - File `.docx`/`.json` sinh ra hợp lệ

- [ ] **Step 5.3: Chạy toàn bộ test suite, không được regression**

```bash
docker compose exec backend pytest backend/tests/ -v
```

---

## Task 6 — Cập nhật CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 6.1: Thêm dòng vào bảng "Quyết định quan trọng & lý do"**

```markdown
| tingia.gov.vn: chuyển từ listing-page 1 trang sang sitemap curated (`parsing_rules.sitemap_pages`, 5/18 sub-sitemap) | Xác nhận thật (curl 2026-07-08): sitemap.xml top-level là `<urlset>` phẳng (không phải `<sitemapindex>`) trộn 18 sub-sitemap `.xml` (chia theo CHỦ ĐỀ, không theo ngày) + 3 trang tĩnh, mọi `<lastmod>` đóng băng cùng timestamp build — không dùng được cơ chế index/`_SITEMAP_DATE_PATTERNS` hiện có. User tự chọn đúng 5/18 sub-sitemap liên quan; dedup URL theo tag cross-sub-sitemap để tránh crawl trùng 1 bài |
```

- [ ] **Step 6.2: Cập nhật đoạn "Verify Slice 2"/"Trạng thái hiện tại"**

Sửa các chỗ còn ghi TinGia dùng "listing crawler" thành sitemap-based, và cập nhật kết quả verify job thật ở Task 5 (số bài crawl được, có/không dedup phát huy tác dụng thật).

- [ ] **Step 6.3: Xóa/cập nhật gap "TinGia chưa verify job thật" trong "Vấn đề cần làm rõ"** (nếu Task 5 verify thành công)

- [ ] **Step 6.4: Commit**

```bash
git add backend/crawler/sitemap.py backend/tests/test_sitemap.py backend/tests/test_report_job.py \
        backend/alembic/versions/0006_tingia_sitemap_pages.py CLAUDE.md
git commit -m "feat: tingia.gov.vn chuyển từ listing-page sang crawl sitemap curated (sitemap_pages)

Sitemap.xml gốc là urlset phẳng lastmod đóng băng, sub-sitemap chia theo chủ đề
không theo ngày — không dùng được cơ chế index hiện có. Dùng danh sách 5 sub-sitemap
curated qua parsing_rules.sitemap_pages (linh hoạt sửa qua migration/DB, không hardcode),
dedup URL cross-sub-sitemap để tránh crawl trùng.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-review checklist

### Spec coverage
- [x] Dùng sitemap thay vì listing-page cho TinGia → Task 2 + Task 4
- [x] Chỉ fetch đúng 5 sub-sitemap đã chọn, không phải toàn bộ 18 → Task 1 Step 1.2, Task 4
- [x] Dedup URL trùng giữa các sub-sitemap → Task 1 Step 1.3, Task 2 Step 2.1
- [x] Cấu hình linh hoạt (không hardcode), sửa được qua migration/DB → `parsing_rules.sitemap_pages`, Task 4
- [x] Xóa code/config cũ outdated của TinGia → Task 4 (migration UPDATE thay `TINGIA_LISTING_RULES`); giữ nguyên `listing.py` (đã xác nhận với user — không phải code riêng TinGia)
- [x] Verify dữ liệu thật trước khi commit (yêu cầu CLAUDE.md workflow) → Task 5

### Ambiguity đã chốt qua hội thoại
- `sitemap_url` TinGia → NULL (nhất quán với BoCongAn `0005`)
- `_get_candidates()` không cần sửa (verify lại bằng Task 3, có test guard)
- `listing.py` giữ nguyên (fallback tổng quát, không phải dead code do task này gây ra)

### Rủi ro còn lại
- Task 3 Step 3.2 là bước tự-kiểm-chứng giả định "không cần sửa `report_job.py`" — nếu FAIL phải quay lại sửa `_get_candidates()`, không phải lỗi nghiêm trọng nhưng cần xử lý trước khi sang Task 4.
