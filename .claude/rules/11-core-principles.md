---
description: Nguyên tắc bắt buộc — data integrity, AI transparency, MVP-first
alwaysApply: true
---

# Nguyên tắc bắt buộc

1. **Không được làm mất dữ liệu gốc** — mọi bài viết phải lưu `url` gốc
2. **Tách biệt dữ liệu thật vs AI** — không trộn lẫn trong báo cáo
3. **Mọi kết luận trong báo cáo phải có nguồn dữ liệu thực tế**
4. **AI confidence < 0.6 phải được đánh dấu** và tách riêng trong output
5. **Không spam request** — đặt delay 1–2s giữa các request đến cùng một domain
6. **MVP-first** — không thêm tính năng ngoài scope trừ khi được yêu cầu rõ ràng
7. **Không tự thêm nguồn dữ liệu mới** — chỉ Admin mới được cấu hình nguồn (`sources`)
