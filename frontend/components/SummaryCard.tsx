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
