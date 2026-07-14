import { Card, Alert, Typography } from "antd";

type Props = {
  sourceCount: number;
  dayCount: number;
};

export default function SummaryCard({ sourceCount, dayCount }: Props) {
  const showWarning = sourceCount >= 5 && dayCount >= 60;

  return (
    <Card size="small" style={{ background: "#fafafa" }}>
      <Typography.Text strong>
        {sourceCount} nguồn · {dayCount} ngày
      </Typography.Text>
      {showWarning && (
        <Alert
          style={{ marginTop: 8 }}
          type="warning"
          showIcon
          message="Job sẽ chạy nền, có thể mất nhiều thời gian với số nguồn/ngày lớn — sẽ thông báo khi xong."
        />
      )}
    </Card>
  );
}
