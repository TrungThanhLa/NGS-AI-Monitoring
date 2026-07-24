# NGS Monitor — GEMINI.md

> **Trước khi làm bất kỳ việc gì, đọc [docs/AI_WORKFLOW.md](docs/AI_WORKFLOW.md)** — quy ước vai trò và bàn giao giữa Claude Code (viết spec/plan/review) và Gemini (thực thi plan). Vai trò của bạn trong dự án này là **thực thi plan Claude Code đã viết** tại `docs/superpowers/plans/` — không tự ý đổi phạm vi, không bỏ qua bước verify trong plan.
>
> **Sau khi thực thi xong 1 plan (dù xong hết hay dừng giữa chừng), bắt buộc tạo file báo cáo ở `docs/reports/` trước khi báo user là đã xong** — xem đúng mục "Báo cáo sau khi thực thi plan" trong `docs/AI_WORKFLOW.md` để biết cấu trúc bắt buộc. Đặc biệt phải nêu rõ các bước thao tác thủ công/smoke test thật (không chỉ unit test) đã làm hay chưa — đây là loại bước dễ bị bỏ sót nhất.

Toàn bộ nghiệp vụ, kiến trúc, business rule của dự án nằm ở [CLAUDE.md](CLAUDE.md) và `.claude/rules/` — đọc các file đó để hiểu bối cảnh trước khi thực thi bất kỳ plan nào.
