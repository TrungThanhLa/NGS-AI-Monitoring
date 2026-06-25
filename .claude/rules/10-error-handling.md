---
description: Xử lý ngoại lệ — crawler, AI, dedup, job timeout
alwaysApply: true
---

# Ngoại lệ & Cách xử lý

| Tình huống | Xử lý |
|---|---|
| Crawler timeout / bị block | Retry 3 lần (exponential backoff), log lỗi, tiếp tục với nguồn khác |
| Website không có sitemap | Tự động fallback sang listing page crawler |
| Dữ liệu trùng lặp | Check SHA256(url) trước khi insert — bỏ qua nếu đã tồn tại |
| AI confidence < 0.6 | Flag `needs_review=true`, vẫn lưu và đưa vào báo cáo |
| AI trả về JSON không hợp lệ | Parse với try/except, retry 1 lần, nếu vẫn lỗi thì skip bài đó |
| Job chạy quá lâu | Chạy nền qua Celery, FE polling mỗi 3 giây |
| Website dùng JavaScript render | Playwright thay thế httpx cho nguồn đó |
