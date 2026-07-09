# Nguyên tắc hành vi khi code

> Bổ sung (không thay thế) cho [11 · Core Principles](11-core-principles.md) (nguyên tắc nghiệp vụ/dữ liệu) và [13 · Workflow](13-workflow.md) (quy trình EPCC).

### 1. Suy nghĩ trước khi code — không tự giả định
Khi yêu cầu chưa rõ (CSS selector cho nguồn mới, ngưỡng confidence đặc biệt, placeholder DOCX chưa định nghĩa...), dừng lại và hỏi thay vì đoán.
- Nêu rõ giả định trước khi code; nếu có điểm chưa chắc — hỏi lại user
- Nếu có nhiều cách hiểu yêu cầu, trình bày các cách hiểu — không tự chọn 1 cách rồi im lặng code
- Nếu có cách làm đơn giản hơn cách user đề xuất, nói rõ và đề xuất — không ngại phản biện
- Đây là phần mở rộng cho bước Explore của EPCC ([13 · Workflow](13-workflow.md))

### 2. Tối giản — không thêm thứ ngoài yêu cầu
Theo đúng nguyên tắc MVP-first đã có ([11 · Core Principles](11-core-principles.md)): mọi đoạn code mới phải là lượng code tối thiểu giải quyết đúng yêu cầu.
- Không thêm feature, config, hay "khả năng mở rộng" nếu không được yêu cầu rõ
- Không tạo abstraction (lớp trừu tượng/helper dùng chung) cho code chỉ dùng 1 lần
- Không viết error handling cho tình huống không thể xảy ra trong context hiện tại (xem case đã định nghĩa ở [10 · Error Handling](10-error-handling.md))
- Ngoại lệ: thiết kế linh hoạt đã chốt trong schema (VD: `sources.parsing_rules` JSONB) là quyết định kiến trúc có chủ đích — không tính là "thêm ngoài yêu cầu"

### 3. Sửa đúng phạm vi — không "tiện tay" sửa thêm
Chỉ đụng vào phần code liên quan trực tiếp tới yêu cầu.
- Không "cải thiện" code/comment/format ở đoạn không liên quan
- Không refactor code đang chạy tốt nếu không được yêu cầu
- Giữ đúng style hiện có của file, kể cả quy ước comment tiếng Việt giải thích logic quan trọng ([13 · Workflow](13-workflow.md))
- Phát hiện dead code không liên quan tới task → báo cho user biết, không tự xóa
- Chỉ dọn import/biến/function không dùng nữa nếu chính thay đổi của bạn gây ra — không dọn dead code có từ trước

### 4. Làm theo tiêu chí xác minh được — verify trước khi báo "xong"
Mọi task phải quy về tiêu chí kiểm tra được, không dừng ở "chạy được là xong".
- "Thêm validate nguồn" → viết test case cho input không hợp lệ, rồi làm nó pass
- "Sửa bug crawler/AI pipeline" → viết test reproduce lỗi trước, rồi mới fix
- "Refactor parser/aggregator" → đảm bảo test pass cả trước và sau khi sửa
- Với task nhiều bước, nêu ngắn gọn plan dạng: `1. [Bước] → verify: [cách kiểm tra]`
- Vẫn phải tuân thủ bước Commit của EPCC: lint + type check + test với ít nhất 1 nguồn dữ liệu thật trước khi commit ([13 · Workflow](13-workflow.md))
