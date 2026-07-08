# Thêm nguồn vietnam.vn — sitemap chia theo NGÀY (single-day convention mới)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development khi code — viết test FAIL trước, code sau. Steps dùng checkbox (`- [ ]`) để track.

**Goal:** Thêm nguồn thứ 7 `vietnam.vn` — đã verify thật (curl 2026-07-08): top-level `https://www.vietnam.vn/sitemap.xml` LÀ `<sitemapindex>` thật (không phải flat urlset như TinGia/BoCongAn), chứa 1301 sub-sitemap gồm 1285 file `sitemap/sitemap-post/YYYY-MM-DD.xml` (mỗi ngày 1 file, `<lastmod>` thật riêng biệt từng bài, KHÔNG đóng băng) + 16 sub-sitemap khác không phải bài viết (`sitemap-page.xml`, `sitemap-author.xml`, `sitemap-organization.xml`, `sitemap-category.xml`, `sitemap-tag.xml` + 10 file `sitemap-tag/{số}.xml`, `news-sitemap.xml`).

Vì sub-sitemap chia theo NGÀY thật (không phải theo chủ đề như TinGia), dùng lại đúng cơ chế `_SITEMAP_DATE_PATTERNS` hiện có (giống VTV/VOV/VietnamPlus/CAND) — **không** dùng `parsing_rules.sitemap_pages` curated thủ công. Nhưng cơ chế hiện tại (`_sub_sitemap_date_range`) chỉ hỗ trợ 2 convention (`day_start`+`day_end` = khoảng ngày trong tháng kiểu VTV; chỉ `year`+`month` = cả tháng kiểu VOV/VN+/CAND) — **chưa có convention "đúng 1 ngày/file"**. Cần thêm named group thứ 3: `day` (đơn lẻ).

16 sub-sitemap không phải bài viết sẽ **tự động bị loại** (không cần code exclude riêng) vì không khớp regex `sitemap-post/YYYY-MM-DD.xml` — đúng theo quyết định đã có "Sub-sitemap không khớp pattern của domain → bỏ qua hoàn toàn, KHÔNG fallback fetch-all".

Đã xác nhận với user: nguồn liên quan đúng phạm vi dự án (dù nội dung đa dạng, tương tự VTV/VOV không chuyên tin giả) — không thêm lọc chủ đề ở bước crawl, để AI (Slice 3) tự phân loại. Verify job thật vẫn dùng chung `MAX_ARTICLES_PER_JOB=4`, không set riêng cho nguồn này.

**Architecture:**
- `_sub_sitemap_date_range()` (`sitemap.py`): thêm nhánh thứ 3 — `if groups.get("day") is not None: return date(year, month, day), date(year, month, day)` (đặt sau nhánh `day_start`, trước nhánh month-only).
- `_SITEMAP_DATE_PATTERNS["vietnam.vn"] = re.compile(r"sitemap-post/(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})\.xml$")`
- Migration `0007`: seed nguồn mới `vietnam.vn` (`source_id=00000000-0000-0000-0000-000000000007`, `sitemap_url="https://www.vietnam.vn/sitemap.xml"`, `parsing_rules={"engine": "crawl4ai"}` — đã verify thật trang bài viết SSR (nội dung `<p>` thật trong HTML tĩnh, không cần Playwright), `group_name="Vietnam.vn"` (nhóm riêng, không thuộc nhóm nào có sẵn)).
- **Không cần sửa `report_job.py`/`listing.py`** — vietnam.vn đi thẳng qua nhánh `get_article_urls()` sẵn có (có `sitemap_url`, không có `listing_url`/`listing_pages`/`sitemap_pages`).

**Tech Stack:** Python, pytest, httpx.MockTransport, Alembic

---

## Mapping file → trách nhiệm sau khi sửa

| File | Thay đổi |
|---|---|
| `backend/crawler/sitemap.py` | Thêm nhánh `day` (đơn lẻ) trong `_sub_sitemap_date_range()`; thêm entry `"vietnam.vn"` vào `_SITEMAP_DATE_PATTERNS` |
| `backend/tests/test_sitemap.py` | Thêm `VietnamVNSource`; 3 test mới |
| `backend/alembic/versions/0007_seed_vietnamvn_source.py` | Migration mới — seed nguồn `vietnam.vn` |
| `CLAUDE.md` | Ghi quyết định mới, cập nhật số nguồn Slice 2 (6 → 7) |

---

## Task 1 — Viết failing tests cho convention "1 ngày/file" + pattern `vietnam.vn`

**Files:**
- Modify: `backend/tests/test_sitemap.py`

- [ ] **Step 1.1: Thêm `VietnamVNSource` class** (đặt cạnh `CANDSource`)

```python
class VietnamVNSource:
    """vietnam.vn: sub-sitemap chia đúng 1 ngày/file (sitemap-post/YYYY-MM-DD.xml) — convention mới, khác VTV (khoảng ngày) và VOV/VN+/CAND (cả tháng)."""
    sitemap_url = "https://www.vietnam.vn/sitemap.xml"
    domain = "vietnam.vn"
    parsing_rules = {}
```

- [ ] **Step 1.2: Test pre-filter theo đúng 1 ngày/file**

```python
def test_vietnamvn_domain_pre_filters_by_exact_day():
    # domain="vietnam.vn" → regex day đơn lẻ → chỉ fetch sub-sitemap của đúng ngày giao yêu cầu
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-post/2026-07-05.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-post/2026-07-08.xml</loc></sitemap>
</sitemapindex>"""
    sub_sitemap_08 = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://www.vietnam.vn/bai-viet-ngay-08</loc>
        <lastmod>2026-07-08T04:04:10.339Z</lastmod>
    </url>
</urlset>"""
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        if "2026-07-08" in str(request.url):
            return httpx.Response(200, text=sub_sitemap_08)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        VietnamVNSource(), date_from=date(2026, 7, 8), date_to=date(2026, 7, 8),
        client=client, delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://www.vietnam.vn/bai-viet-ngay-08"]
    assert "https://www.vietnam.vn/sitemap/sitemap-post/2026-07-05.xml" not in requested
    assert failed_locs == []
```

- [ ] **Step 1.3: Test 16 sub-sitemap không phải bài viết bị bỏ qua hoàn toàn (không fetch)**

```python
def test_vietnamvn_skips_non_post_sub_sitemaps_when_domain_has_pattern():
    # sitemap-page/author/organization/category/tag/tag-N/news-sitemap không khớp
    # pattern "sitemap-post/YYYY-MM-DD.xml" → bị bỏ qua hoàn toàn, KHÔNG fetch (verify thật
    # 2026-07-08: đây là trang tĩnh/tác giả/tổ chức/danh mục/tag, không phải bài viết).
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://www.vietnam.vn/news-sitemap.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-page.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-author.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-organization.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-category.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-tag.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-tag/220001.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-post/2026-07-08.xml</loc></sitemap>
</sitemapindex>"""
    sub_sitemap_08 = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://www.vietnam.vn/bai-that</loc><lastmod>2026-07-08T04:04:10.339Z</lastmod></url>
</urlset>"""
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        if "sitemap-post/2026-07-08" in str(request.url):
            return httpx.Response(200, text=sub_sitemap_08)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        VietnamVNSource(), date_from=date(2026, 7, 1), date_to=date(2026, 7, 8),
        client=client, delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://www.vietnam.vn/bai-that"]
    assert len(requested) == 2  # /sitemap.xml (index) + đúng 1 sub-sitemap post khớp pattern
```

- [ ] **Step 1.4: Test khoảng ngày giao nhiều file (2 ngày liên tiếp)**

```python
def test_vietnamvn_fetches_multiple_days_when_range_spans_several_files():
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-post/2026-07-07.xml</loc></sitemap>
    <sitemap><loc>https://www.vietnam.vn/sitemap/sitemap-post/2026-07-08.xml</loc></sitemap>
</sitemapindex>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if "2026-07-07" in str(request.url):
            return httpx.Response(
                200,
                text='<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                '<url><loc>https://www.vietnam.vn/bai-07</loc><lastmod>2026-07-07T10:00:00Z</lastmod></url>'
                "</urlset>",
            )
        if "2026-07-08" in str(request.url):
            return httpx.Response(
                200,
                text='<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                '<url><loc>https://www.vietnam.vn/bai-08</loc><lastmod>2026-07-08T10:00:00Z</lastmod></url>'
                "</urlset>",
            )
        return httpx.Response(200, text=index_xml)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        VietnamVNSource(), date_from=date(2026, 7, 7), date_to=date(2026, 7, 8),
        client=client, delay_seconds=0,
    )

    assert sorted(item["url"] for item in result) == ["https://www.vietnam.vn/bai-07", "https://www.vietnam.vn/bai-08"]
```

- [ ] **Step 1.5: Chạy để xác nhận FAIL (expected — domain chưa có trong dict, `day` group chưa xử lý)**

```bash
docker compose exec backend pytest backend/tests/test_sitemap.py -k vietnamvn -v
```

---

## Task 2 — Implement: thêm convention `day` + entry `vietnam.vn`

**Files:**
- Modify: `backend/crawler/sitemap.py`

- [ ] **Step 2.1: Thêm nhánh `day` trong `_sub_sitemap_date_range()`**

Tìm:
```python
    if groups.get("day_start") is not None:
        return date(year, month, int(groups["day_start"])), date(year, month, int(groups["day_end"]))

    day_end = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, day_end)
```

Thay bằng:
```python
    if groups.get("day_start") is not None:
        return date(year, month, int(groups["day_start"])), date(year, month, int(groups["day_end"]))

    if groups.get("day") is not None:
        exact_day = date(year, month, int(groups["day"]))
        return exact_day, exact_day

    day_end = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, day_end)
```

- [ ] **Step 2.2: Thêm entry vào `_SITEMAP_DATE_PATTERNS`**

```python
    # VD: https://www.vietnam.vn/sitemap/sitemap-post/2026-7-8.xml (verified 2026-07-08) —
    # chia đúng 1 ngày/file, khác VTV (khoảng ngày)/VOV,VN+,CAND (cả tháng).
    "vietnam.vn": re.compile(
        r"sitemap-post/(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})\.xml$"
    ),
```

- [ ] **Step 2.3: Chạy lại test Task 1 — phải PASS**

```bash
docker compose exec backend pytest backend/tests/test_sitemap.py -k vietnamvn -v
```

- [ ] **Step 2.4: Chạy toàn bộ `test_sitemap.py` — không được regression**

```bash
docker compose exec backend pytest backend/tests/test_sitemap.py -v
```

---

## Task 3 — Migration `0007`: seed nguồn `vietnam.vn`

**Files:**
- Create: `backend/alembic/versions/0007_seed_vietnamvn_source.py`

- [ ] **Step 3.1: Viết migration**

```python
"""seed nguồn mới vietnam.vn (sitemap chia theo ngày)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-08
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

SOURCE_ID = "00000000-0000-0000-0000-000000000007"
PARSING_RULES = json.dumps({"engine": "crawl4ai"})


def upgrade():
    op.execute(
        sa.text(
            """
            INSERT INTO sources
                (source_id, name, domain, group_name, sitemap_url, listing_url, parsing_rules, is_active)
            VALUES
                (:source_id, 'Vietnam.vn', 'vietnam.vn', 'Vietnam.vn',
                 'https://www.vietnam.vn/sitemap.xml', NULL, CAST(:parsing_rules AS jsonb), true)
            ON CONFLICT (domain) DO NOTHING
            """
        ).bindparams(source_id=SOURCE_ID, parsing_rules=PARSING_RULES)
    )


def downgrade():
    op.execute(sa.text("DELETE FROM sources WHERE domain = 'vietnam.vn'"))
```

- [ ] **Step 3.2: Chạy migration thật**

```bash
docker compose exec backend sh -c "cd /app/backend && alembic upgrade head"
```

- [ ] **Step 3.3: Verify DB**

```bash
docker compose exec postgres psql -U ngs -d ngs_monitor -c "SELECT domain, sitemap_url, parsing_rules FROM sources WHERE domain = 'vietnam.vn';"
```

---

## Task 4 — Verify thật với dữ liệu thật

- [ ] **Step 4.1: Restart `celery-worker`** (bài học từ TinGia — module Python đã import vào memory, mount volume không tự nạp lại code mới)

```bash
docker compose restart celery-worker
```

- [ ] **Step 4.2: Chạy job thật** — `source_ids=[vietnam.vn]`, `date_from=2026-07-07`, `date_to=2026-07-08` (2 ngày, tránh trùng ngày do API từ chối `date_from >= date_to`), `MAX_ARTICLES_PER_JOB=4` (giữ nguyên, không đổi riêng cho nguồn này — theo quyết định đã chốt với user)

- [ ] **Step 4.3: Poll tới `completed`, kiểm tra:**
  - `crawled=analyzed=4`, không có `status="error"`
  - URL bài viết thuộc đúng `sitemap-post/2026-07-07.xml` hoặc `2026-07-08.xml` (không lẫn URL `/tag/`, `/category/`, `/authors/`...)
  - `.docx`/`.json` hợp lệ

- [ ] **Step 4.4: Chạy toàn bộ test suite**

```bash
docker compose exec backend pytest backend/tests/ -v
```

---

## Task 5 — Cập nhật CLAUDE.md + Commit

- [ ] **Step 5.1: Thêm dòng vào bảng "Quyết định quan trọng"** — convention `day` mới trong `_sub_sitemap_date_range`, lý do (vietnam.vn chia đúng 1 ngày/file, khác 2 convention cũ)
- [ ] **Step 5.2: Cập nhật số nguồn Slice 2** — 6 → 7 nguồn thật
- [ ] **Step 5.3: Cập nhật "Trạng thái hiện tại"/"Verify Slice 2"** với kết quả Task 4
- [ ] **Step 5.4: Commit**

```bash
git add backend/crawler/sitemap.py backend/tests/test_sitemap.py \
        backend/alembic/versions/0007_seed_vietnamvn_source.py CLAUDE.md
git commit -m "$(cat <<'EOF'
feat: thêm nguồn vietnam.vn — sitemap chia theo ngày (convention day mới)

Sub-sitemap dạng sitemap-post/YYYY-MM-DD.xml, mỗi ngày 1 file, lastmod thật
riêng biệt (khác TinGia đóng băng theo chủ đề). Thêm convention "day" đơn lẻ
vào _sub_sitemap_date_range() (khác day_start/day_end và month-only đã có),
tái dùng cơ chế _SITEMAP_DATE_PATTERNS sẵn có — không cần sitemap_pages curated.
16 sub-sitemap không phải bài viết (page/author/organization/category/tag×11/
news) tự động bị loại vì không khớp pattern.

Đã verify job thật thành công.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-review checklist

### Spec coverage
- [x] Nhận diện đúng cấu trúc sitemap thật (index thật, sub-sitemap theo ngày) → verify curl trước khi viết plan
- [x] Convention mới "1 ngày/file" → Task 1 + Task 2
- [x] 16 sub-sitemap không phải bài viết tự động loại, không cần code riêng → Task 1 Step 1.3
- [x] Seed nguồn mới qua migration → Task 3
- [x] Verify dữ liệu thật trước khi commit → Task 4
- [x] Đã xác nhận với user: đúng nguồn mong muốn, không lọc chủ đề ở bước crawl, dùng chung `MAX_ARTICLES_PER_JOB`

### Rủi ro đã biết
- 1576 bài/ngày là khối lượng lớn — job thật ngoài phạm vi verify (không giới hạn `MAX_ARTICLES_PER_JOB`) sẽ rất nặng cho AI CPU-only; đã xác nhận với user đây là vấn đề để dành Slice 3, không xử lý ở task này
- Nhớ `docker compose restart celery-worker` sau khi sửa `sitemap.py` (bài học thật từ TinGia)
