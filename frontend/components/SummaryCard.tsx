type Props = {
  sourceCount: number;
  dayCount: number;
};

export default function SummaryCard({ sourceCount, dayCount }: Props) {
  const showWarning = sourceCount >= 5 && dayCount >= 60;

  return (
    <div className="border rounded p-3 bg-gray-50">
      <p className="font-medium">
        {sourceCount} nguồn · {dayCount} ngày
      </p>
      {showWarning && (
        <p className="text-amber-700 text-sm mt-2">
          ⚠️ Job sẽ chạy nền, có thể mất nhiều thời gian với số nguồn/ngày lớn — sẽ thông báo khi xong.
        </p>
      )}
    </div>
  );
}
