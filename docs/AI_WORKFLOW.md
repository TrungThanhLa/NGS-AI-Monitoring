# Quy ước làm việc giữa Claude Code và Gemini (Antigravity)

> File này là nơi thống nhất **vai trò** và **quy ước bàn giao** giữa 2 công cụ AI dùng cho dự án này — không lặp lại nghiệp vụ/kiến trúc đã có ở `CLAUDE.md` và `.claude/rules/`. Cả Claude Code (đọc `CLAUDE.md`) và Gemini/Antigravity (đọc `GEMINI.md`) đều phải đọc file này **trước khi làm bất kỳ việc gì** — 2 AI không chia sẻ context với nhau, file này là điểm đồng bộ duy nhất ngoài chính source code.

## Vai trò cố định

| AI | Vai trò | Không được làm |
|---|---|---|
| **Claude Code** | Phân tích vấn đề, brainstorm, viết spec, viết plan (kèm test fail trước theo TDD), review code sau khi thực thi xong | Không tự thực thi plan dài trong cùng 1 session nếu mục đích là để Gemini thực thi (tránh trùng việc, tốn context 2 lần) |
| **Gemini (Antigravity)** | Thực thi plan Claude Code đã viết — code, tự chạy test, tự verify theo skill `superpowers` đã cài | Không tự ý đổi phạm vi/quyết định kiến trúc đã chốt trong plan; không tự bỏ qua bước verify; không tự viết spec/plan mới thay Claude Code |

## Nơi lưu spec/plan

- Spec: `docs/superpowers/specs/YYYY-MM-DD-<tên>-design.md`
- Plan: `docs/superpowers/plans/YYYY-MM-DD-<tên>-plan.md`
- Gemini thực thi đúng plan tại đường dẫn trên — không nhận plan qua chat rời rạc để tránh mất bản ghi.

## Quy ước bàn giao qua lại

1. **Claude Code → Gemini:** sau khi viết xong spec + plan, Claude Code báo rõ đường dẫn file plan cho user để user đưa qua Antigravity — không giao cả roadmap nhiều Phase cùng lúc, giao **từng Phase một**.
2. **Gemini → Claude Code:** sau khi 1 Phase thực thi xong, Gemini **bắt buộc phải tạo file báo cáo** ở `docs/reports/` (xem mục "Báo cáo sau khi thực thi plan" dưới đây) trước khi báo cho user là đã xong. User đưa đường dẫn file báo cáo này cho Claude Code (resume session cũ nếu còn, hoặc session mới) để review + verify trước khi viết plan cho Phase kế tiếp — không chuyển sang Phase sau khi chưa review Phase trước.
3. **Cập nhật trạng thái:** chỉ Claude Code cập nhật mục "Trạng thái dự án & Quyết định quan trọng" trong `CLAUDE.md`, rule tương ứng (`.claude/rules/*.md`), và tick checkbox `- [x]` trong file plan — sau khi đã **tự** xác nhận (đọc báo cáo + tự chạy lại lệnh verify, không tin lời báo cáo suông) Phase đó thật sự xong. Không cập nhật tài liệu chỉ dựa trên nội dung báo cáo mà chưa kiểm chứng lại bằng chính tay Claude Code.

## Báo cáo sau khi thực thi plan (`docs/reports/`)

Sau khi thực thi xong 1 plan (dù xong toàn bộ hay dừng giữa chừng), Gemini **bắt buộc** tạo 1 file báo cáo trước khi báo cho user là đã xong:

- **Đường dẫn:** `docs/reports/YYYY-MM-DD-<cùng-tên-slug-với-plan>-report.md` (VD plan `docs/superpowers/plans/2026-07-23-continuous-discover-per-campaign-window-plan.md` → report `docs/reports/2026-07-23-continuous-discover-per-campaign-window-report.md`).
- **Bắt buộc phải có các mục sau, không thiếu mục nào:**

  1. **Bảng trạng thái từng Task** — theo đúng số Task/Step trong plan gốc, mỗi Task ghi rõ 1 trong 3 trạng thái: `✅ Xong` / `⚠️ Dở dang` / `❌ Chưa làm`, kèm commit hash tương ứng (nếu có).
  2. **Bằng chứng verify thật** — dán nguyên văn output thật của các lệnh `Verify:`/`Run:` đã chạy trong plan (không diễn giải bằng lời, phải là output thật) — đặc biệt các bước **thao tác thủ công qua UI/Docker thật** (VD smoke test tạo Campaign thật, bật công tắc, đợi Celery Beat chạy) — đây là loại bước dễ bị bỏ sót nhất, phải nêu rõ đã làm hay chưa, không được ngầm định "code xong = coi như đã test".
  3. **Việc còn tồn đọng** — liệt kê rõ Task/Step nào chưa làm hoặc làm dở, vì sao (hết thời gian, gặp lỗi chưa giải quyết được, cần quyết định của user...).
  4. **Sai khác so với plan** — bất kỳ chỗ nào code/test thực tế khác với plan gốc (dù nhỏ, dù không phải bug) — không được tự ý đổi mà không ghi chú lại.
  5. **Cần lưu ý / cần quyết định** — rủi ro phát hiện được trong lúc thực thi, giả định phải tự đưa ra vì plan chưa nói rõ, hoặc điểm cần user/Claude Code quyết định tiếp.

- Đây không phải tài liệu nghiệp vụ lâu dài — không đưa nội dung report thẳng vào `CLAUDE.md`/rule; đó là việc của Claude Code làm sau khi đã tự verify lại nội dung report.
- Chưa tick checkbox `- [ ]` trong file plan — nhiệm vụ của Gemini là **báo cáo trung thực trạng thái thật**, việc tick checkbox chính thức là của Claude Code (mục 3, "Quy ước bàn giao qua lại" ở trên) sau khi tự verify.

## Ràng buộc bắt buộc khi giao việc cho Gemini

- Mọi task giao cho Gemini phải có tiêu chí verify khách quan đi kèm (lệnh chạy test/lint cụ thể + kết quả kỳ vọng) — không giao task chỉ mô tả bằng lời.
- Nếu 1 bước verify fail, Gemini phải dừng lại và không tự ý bỏ qua sang bước tiếp theo.
- Test thật với dữ liệu thật (rule 13 Workflow) vẫn áp dụng — Gemini không được báo "xong" khi chưa chạy thử thật.

## Ghi chú

- Đã xác nhận: `superpowers` cài được cho Antigravity qua `agy plugin install https://github.com/obra/superpowers`, tự kích hoạt từ tin nhắn đầu qua session-start hook — nhưng **mức độ tuân thủ skill giữa Gemini và Claude chưa được đảm bảo giống nhau**, cần theo dõi thực tế và điều chỉnh lại quy ước này nếu phát hiện Gemini bỏ qua bước verify.
