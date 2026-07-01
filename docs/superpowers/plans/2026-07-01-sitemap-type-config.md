# Sitemap Per-Domain Pattern Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thay 2 regex chung `_DATE_RANGE_RE`/`_YEAR_MONTH_RE` (dễ false-positive, khó maintain khi thêm nguồn mới) bằng dict `_SITEMAP_DATE_PATTERNS` với key là domain, value là regex riêng có named groups cho từng site. Không cần thêm gì vào `parsing_rules` JSONB — `source.domain` đã có sẵn trong DB.

**Architecture:**
- `_SITEMAP_DATE_PATTERNS: dict[str, re.Pattern]` trong `sitemap.py` — mỗi domain một regex tường minh
- Named groups phân loại hành vi tự động: `year+month+day_start+day_end` → khoảng ngày trong tháng; `year+month` (không có `day_*`) → toàn bộ tháng
- `_sub_sitemap_date_range(loc, pattern)` nhận `re.Pattern | None` thay vì `str` — không còn logic rẽ nhánh theo type string
- `get_article_urls` đọc `source.domain` để lookup pattern, không đọc `parsing_rules`
- Domain không có trong dict → `pattern=None` → không pre-filter, fetch tất cả (safe fallback)
- **Không cần migration** — domain đã có sẵn trong `sources.domain`, không thêm column hay JSONB key mới

**Tech Stack:** Python, pytest, httpx.MockTransport

---

## Mapping file → trách nhiệm sau khi sửa

| File | Thay đổi |
|---|---|
| `backend/crawler/sitemap.py` | Xóa `_DATE_RANGE_RE`/`_YEAR_MONTH_RE`; thêm `_SITEMAP_DATE_PATTERNS`; `_sub_sitemap_date_range(loc, pattern)` nhận `re.Pattern \| None`; `get_article_urls` lookup `_SITEMAP_DATE_PATTERNS.get(source.domain)` |
| `backend/tests/test_sitemap.py` | Thêm `domain` vào `FakeSource`; thêm `VTVSource`, `VOVSource`; thêm 3 test mới; sửa 3 test cũ bị break |
| `CLAUDE.md` | Thêm dòng vào bảng "Quyết định quan trọng", xóa mục false-positive khỏi "Vấn đề cần làm rõ" |

> **VietnamPlus và CAND:** chưa có URL sub-sitemap thật được verify → chưa thêm vào dict. Hai nguồn này tạm dùng fetch-all fallback (an toàn). Điền sau khi chạy `curl` lấy URL thật từ sitemap của từng nguồn và xác nhận pattern bằng Python shell.

---

## Bước tiền quyết — Verify URL sub-sitemap thật của VN+ và CAND

Trước khi bắt tay vào code, cần lấy URL thật để điền regex đúng.

```bash
# Lấy danh sách sub-sitemap URL thật
curl -s https://www.vietnamplus.vn/sitemap.xml | grep -oP 'https://[^<]+'
curl -s https://cand.vn/sitemap.xml | grep -oP 'https://[^<]+'
```

Paste một vài URL vào Python shell và test regex:

```python
import re

# Điều chỉnh pattern cho đúng với URL thật quan sát được
pattern = re.compile(r"/(?P<year>\d{4})/(?P<month>\d{1,2})/")
print(pattern.search("https://...url-that/...").groupdict())
```

Sau đó điền vào `_SITEMAP_DATE_PATTERNS` trước Task 2. Nếu pattern giống VOV (`/YYYY/M/`) thì dùng lại cùng regex string — **nhưng vẫn khai riêng từng domain**, không dùng chung 1 compiled object (để sau này site đổi format chỉ sửa 1 dòng, không ảnh hưởng site kia).

---

## Task 1 — Viết failing tests cho behavior per-domain pattern

**Files:**
- Modify: `backend/tests/test_sitemap.py`

- [ ] **Step 1.1: Thêm `domain` vào `FakeSource` và thêm `VTVSource`, `VOVSource`**

Tìm class `FakeSource` và thay bằng:

```python
class FakeSource:
    """Domain không có trong _SITEMAP_DATE_PATTERNS → pattern=None → fetch-all (safe fallback)."""
    sitemap_url = "https://vtv.vn/sitemap.xml"
    domain = "unknown.example.com"


class VTVSource:
    """VTV: regex khoảng ngày trong tháng (day_start + day_end)."""
    sitemap_url = "https://vtv.vn/sitemap.xml"
    domain = "vtv.vn"


class VOVSource:
    """VOV: regex năm-tháng, path-based (/YYYY/M/)."""
    sitemap_url = "https://vov.vn/sitemap.xml"
    domain = "vov.vn"
```

- [ ] **Step 1.2: Thêm 3 test mới vào cuối file**

Thêm sau test cuối cùng (`test_fetches_sub_sitemap_with_unrecognized_name_pattern_instead_of_skipping`):

```python
def test_vtv_domain_pre_filters_by_date_range():
    # domain="vtv.vn" → regex day_start/day_end → chỉ fetch sub-sitemap giao với yêu cầu
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://vtv.vn/sitemaps/sitemaps-2026-6-01-10.xml</loc></sitemap>
    <sitemap><loc>https://vtv.vn/sitemaps/sitemaps-2026-6-21-25.xml</loc></sitemap>
</sitemapindex>"""
    sub_sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://vtv.vn/bai-viet-ngay-22.htm</loc>
        <lastmod>2026-06-22T10:00:00+07:00</lastmod>
    </url>
</urlset>"""
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        if "6-21-25" in str(request.url):
            return httpx.Response(200, text=sub_sitemap)
        raise AssertionError(f"unexpected request: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        VTVSource(), date_from=date(2026, 6, 20), date_to=date(2026, 6, 24),
        client=client, delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://vtv.vn/bai-viet-ngay-22.htm"]
    assert "https://vtv.vn/sitemaps/sitemaps-2026-6-01-10.xml" not in requested
    assert failed_locs == []


def test_vov_domain_pre_filters_by_year_month():
    # domain="vov.vn" → regex year/month path-based → chỉ fetch sub-sitemap của tháng giao yêu cầu
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://vov.vn/sitemaps/2026/4/article.xml</loc></sitemap>
    <sitemap><loc>https://vov.vn/sitemaps/2026/6/article.xml</loc></sitemap>
</sitemapindex>"""
    sub_sitemap_june = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://vov.vn/bai-viet-thang-6-moi</loc>
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
        VOVSource(), date_from=date(2026, 6, 10), date_to=date(2026, 6, 20),
        client=client, delay_seconds=0,
    )

    assert [item["url"] for item in result] == ["https://vov.vn/bai-viet-thang-6-moi"]
    assert "https://vov.vn/sitemaps/2026/4/article.xml" not in requested
    assert failed_locs == []


def test_unknown_domain_fetches_all_sub_sitemaps_as_safe_fallback():
    # domain không có trong _SITEMAP_DATE_PATTERNS → pattern=None → không pre-filter
    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://vtv.vn/sitemaps/sitemaps-2026-6-01-10.xml</loc></sitemap>
    <sitemap><loc>https://vtv.vn/sitemaps/sitemaps-2026-6-21-25.xml</loc></sitemap>
</sitemapindex>"""
    empty_sub = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>"""
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(200, text=index_xml)
        return httpx.Response(200, text=empty_sub)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result, failed_locs = get_article_urls(
        FakeSource(),  # domain="unknown.example.com" → không có trong dict → fetch tất cả
        date_from=date(2026, 6, 20), date_to=date(2026, 6, 24),
        client=client, delay_seconds=0,
    )

    assert "https://vtv.vn/sitemaps/sitemaps-2026-6-01-10.xml" in requested
    assert "https://vtv.vn/sitemaps/sitemaps-2026-6-21-25.xml" in requested
    assert result == []
    assert failed_locs == []
```

- [ ] **Step 1.3: Chạy tests mới để xác nhận FAIL (expected)**

```bash
docker compose exec backend pytest backend/tests/test_sitemap.py::test_vtv_domain_pre_filters_by_date_range backend/tests/test_sitemap.py::test_vov_domain_pre_filters_by_year_month backend/tests/test_sitemap.py::test_unknown_domain_fetches_all_sub_sitemaps_as_safe_fallback -v
```

Expected: **3 FAILED** — `FakeSource` chưa có `domain`, code chưa đọc `source.domain`.

---

## Task 2 — Refactor `sitemap.py`

**Files:**
- Modify: `backend/crawler/sitemap.py`

- [ ] **Step 2.1: Thay 2 regex chung bằng `_SITEMAP_DATE_PATTERNS` dict**

Xóa 2 dòng khai báo `_DATE_RANGE_RE` và `_YEAR_MONTH_RE`, thay bằng:

```python
# Mỗi domain có regex riêng với named groups — không dùng chung regex dễ false-positive.
# Named groups quy ước:
#   year + month + day_start + day_end → sub-sitemap chia theo khoảng ngày trong tháng
#   year + month (không có day_*) → sub-sitemap chia theo tháng, tự tính ngày cuối
# Domain không có entry → pattern=None → không pre-filter, fetch tất cả (safe fallback).
#
# Khi thêm nguồn mới: verify URL thật từ sitemap bằng curl trước khi điền regex,
# không đoán pattern từ tên miền.
_SITEMAP_DATE_PATTERNS: dict[str, re.Pattern] = {
    # VD: https://vtv.vn/sitemaps/sitemaps-2026-6-21-25.xml
    "vtv.vn": re.compile(
        r"sitemaps-(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day_start>\d{1,2})-(?P<day_end>\d{1,2})\.xml$"
    ),
    # VD: https://vov.vn/sitemaps/2026/6/article.xml
    "vov.vn": re.compile(
        r"/(?P<year>\d{4})/(?P<month>\d{1,2})/"
    ),
    # TODO(vietnamplus.vn): điền sau khi verify URL thật (xem bước tiền quyết ở đầu plan)
    # TODO(cand.vn): điền sau khi verify URL thật
}
```

- [ ] **Step 2.2: Thay `_sub_sitemap_date_range` để nhận `pattern` thay vì đoán từ URL**

Xóa toàn bộ hàm `_sub_sitemap_date_range(loc: str)` hiện tại, thay bằng:

```python
def _sub_sitemap_date_range(loc: str, pattern: re.Pattern | None) -> tuple[date, date] | None:
    if pattern is None:
        return None

    match = pattern.search(loc)
    if not match:
        logger.warning("sub-sitemap URL không khớp pattern đã khai: %s", loc)
        return None

    groups = match.groupdict()
    year, month = int(groups["year"]), int(groups["month"])

    if not (1 <= month <= 12):
        logger.warning("month không hợp lệ (%d) trong URL: %s", month, loc)
        return None

    if "day_start" in groups:
        return date(year, month, int(groups["day_start"])), date(year, month, int(groups["day_end"]))

    day_end = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, day_end)
```

- [ ] **Step 2.3: Cập nhật `get_article_urls` để lookup pattern theo domain**

Trong `get_article_urls`, tìm dòng trong vòng `for sitemap_tag in sitemap_tags:`:
```python
            date_range = _sub_sitemap_date_range(loc)
```

Thay toàn bộ vòng `for` đó bằng (pattern lookup đặt trước loop, không lặp lại mỗi iteration):

```python
        pattern = _SITEMAP_DATE_PATTERNS.get(source.domain)
        sub_sitemap_locs = []
        for sitemap_tag in sitemap_tags:
            loc = sitemap_tag.find("loc").get_text(strip=True)
            date_range = _sub_sitemap_date_range(loc, pattern)
```

- [ ] **Step 2.4: Chạy toàn bộ test sitemap để thấy trạng thái hiện tại**

```bash
docker compose exec backend pytest backend/tests/test_sitemap.py -v
```

Expected:
- 3 test mới (Task 1): **PASS** ✓
- `test_returns_only_urls_with_lastmod_inside_date_range_and_skips_irrelevant_sub_sitemaps`: **FAIL** — `FakeSource.domain = "unknown.example.com"` → fetch-all → mock nhận request cho sub-sitemap `11-15` ngoài range → `AssertionError`
- `test_skips_sub_sitemap_that_keeps_failing_after_retries_without_raising`: **FAIL** — cùng lý do, sub-sitemap `11-15` được fetch → mock raise `AssertionError` trước khi đến `21-25`
- `test_recognizes_year_month_only_sub_sitemap_pattern`: **FAIL** — `FakeSource.domain` không có trong dict → fetch-all → mock nhận request cho sub-sitemap tháng 4 → `AssertionError`
- `test_flat_urlset_returns_all_urls_without_lastmod_filtering`: **PASS** ✓ (không qua code path sub-sitemap)
- `test_fetches_sub_sitemap_with_unrecognized_name_pattern_instead_of_skipping`: **PASS** ✓ (`FakeSource.domain` không có trong dict → fetch-all → đúng behavior mong đợi)

---

## Task 3 — Sửa 3 test cũ bị break

**Files:**
- Modify: `backend/tests/test_sitemap.py`

- [ ] **Step 3.1: Sửa `test_returns_only_urls_with_lastmod_inside_date_range_and_skips_irrelevant_sub_sitemaps`**

Đổi `FakeSource()` → `VTVSource()`.

- [ ] **Step 3.2: Sửa `test_skips_sub_sitemap_that_keeps_failing_after_retries_without_raising`**

Đổi `FakeSource()` → `VTVSource()`.

- [ ] **Step 3.3: Sửa `test_recognizes_year_month_only_sub_sitemap_pattern`**

Đổi `FakeSource()` → `VOVSource()`.

- [ ] **Step 3.4: Chạy toàn bộ test sitemap — tất cả phải PASS**

```bash
docker compose exec backend pytest backend/tests/test_sitemap.py -v
```

Expected: **8 passed** (5 cũ + 3 mới).

- [ ] **Step 3.5: Chạy toàn bộ test suite để đảm bảo không có regression**

```bash
docker compose exec backend pytest backend/tests/ -v
```

Expected: tất cả pass.

- [ ] **Step 3.6: Commit**

```bash
git add backend/crawler/sitemap.py backend/tests/test_sitemap.py
git commit -m "refactor: thay 2 regex chung bằng _SITEMAP_DATE_PATTERNS per-domain

_DATE_RANGE_RE/_YEAR_MONTH_RE là regex dùng chung cho mọi site, dễ false-positive
và khó maintain khi thêm nguồn mới dùng cùng kiểu pattern nhưng khác format URL.
Nay mỗi domain có regex riêng với named groups — không cần type string trung gian,
hành vi (khoảng ngày vs toàn tháng) được suy ra từ named groups có trong match.
Domain không khai → fetch-all an toàn.

VietnamPlus/CAND chưa điền (cần verify URL thật trước).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4 — Điền pattern cho VietnamPlus và CAND (sau khi verify thật)

> Làm task này sau khi có URL thật từ bước tiền quyết.

**Files:**
- Modify: `backend/crawler/sitemap.py`
- Modify: `backend/tests/test_sitemap.py`

- [ ] **Step 4.1: Thêm entry vào `_SITEMAP_DATE_PATTERNS`**

Sau khi verify URL thật, thêm vào dict (ví dụ nếu VN+ dùng path `/YYYY/M/`):

```python
    # VD: https://www.vietnamplus.vn/sitemap/2026/6/... (thay bằng URL thật đã verify)
    "vietnamplus.vn": re.compile(
        r"/(?P<year>\d{4})/(?P<month>\d{1,2})/"
    ),
    # VD: https://cand.vn/... (thay bằng URL thật đã verify)
    "cand.vn": re.compile(
        r"..."
    ),
```

- [ ] **Step 4.2: Thêm source class và test cho từng nguồn**

Mỗi nguồn cần:
1. `VietnamPlusSource` và `CANDSource` class trong test file (với `domain` đúng)
2. 1 test verify pre-filter đúng theo URL format đã verify thật

- [ ] **Step 4.3: Chạy lại toàn bộ test suite**

```bash
docker compose exec backend pytest backend/tests/ -v
```

- [ ] **Step 4.4: Commit**

```bash
git add backend/crawler/sitemap.py backend/tests/test_sitemap.py
git commit -m "feat: thêm sitemap pattern cho vietnamplus.vn và cand.vn

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5 — Cập nhật CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 5.1: Thêm dòng vào bảng "Quyết định quan trọng & lý do"**

```markdown
| Thay 2 regex chung `_DATE_RANGE_RE`/`_YEAR_MONTH_RE` bằng `_SITEMAP_DATE_PATTERNS` (dict domain → regex riêng) | 2 regex chung dễ false-positive và ẩn đi việc mỗi site thực ra có format URL khác nhau; khi thêm nguồn mới phải đoán xem nó khớp regex nào. Dict per-domain tường minh hơn: thêm nguồn = thêm 1 entry, đổi format = sửa 1 dòng, không ảnh hưởng site khác. Không cần migration — `source.domain` đã có sẵn (2026-07-01) |
```

- [ ] **Step 5.2: Xóa mục false-positive `_YEAR_MONTH_RE` khỏi "Vấn đề cần làm rõ"**

Tìm và xóa đoạn:
```
- **`_YEAR_MONTH_RE` ở `sitemap.py` (nhận diện sub-sitemap dạng `news-YYYY-M.xml`) có rủi ro false-positive lý thuyết** ...
```

- [ ] **Step 5.3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: ghi nhận quyết định _SITEMAP_DATE_PATTERNS per-domain, đóng vấn đề regex false-positive

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-review checklist

### Spec coverage
- [x] Thay regex chung bằng per-domain dict → Task 2
- [x] Named groups xác định behavior tự động (không cần type string) → Task 2
- [x] Domain không khai → fetch-all an toàn → `pattern=None` path trong `_sub_sitemap_date_range`
- [x] VTV (date_range) và VOV (year_month) có test verify thật → Task 1 + Task 3
- [x] VN+ và CAND: placeholder rõ ràng, không block merge → Task 4 tách riêng
- [x] Không cần migration DB → không có task migration

### So sánh với approach cũ (sitemap_type trong parsing_rules)
| Tiêu chí | Approach cũ (sitemap_type JSONB) | Approach mới (per-domain dict) |
|---|---|---|
| Thêm nguồn mới | Sửa code + chạy migration DB | Chỉ sửa code (1 entry trong dict) |
| Biết format URL | Phải xem `parsing_rules` trong DB | Đọc thẳng trong `sitemap.py` |
| 2 nguồn cùng `year_month` khác format URL | Dùng chung `_YEAR_MONTH_RE`, không phân biệt | Mỗi site regex riêng, tường minh |
| Rollback | Cần downgrade migration | Chỉ revert code |

### Placeholder scan
VN+ và CAND có TODO comment rõ ràng, không có code placeholder ẩn.

### Type consistency
- `_SITEMAP_DATE_PATTERNS: dict[str, re.Pattern]` — khai rõ type
- `_sub_sitemap_date_range(loc: str, pattern: re.Pattern | None)` — nhất quán với dict value type
- `source.domain` — attribute đã có trên SQLAlchemy model `Source` và tất cả test source class
