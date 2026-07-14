"use client";

import { Tag } from "antd";
import MockStatPage from "@/components/mock/MockStatPage";

type AlertRow = {
  id: string;
  title: string;
  type: string;
  level: "Thấp" | "Trung bình" | "Cao" | "Rất cao";
  createdAt: string;
};

const data: AlertRow[] = [
  { id: "1", title: "Từ khóa \"deepfake\" tăng đột biến 350%", type: "Từ khóa", level: "Rất cao", createdAt: "14/07/2026 10:23" },
  { id: "2", title: "Xuất hiện thông tin giả mạo Bộ Công an", type: "Giả mạo", level: "Cao", createdAt: "14/07/2026 09:41" },
  { id: "3", title: "Nhiều bài viết tiêu cực về chính sách mới", type: "Sentiment", level: "Trung bình", createdAt: "14/07/2026 08:55" },
];

const levelColor: Record<AlertRow["level"], string> = {
  "Thấp": "blue",
  "Trung bình": "gold",
  "Cao": "orange",
  "Rất cao": "red",
};

export default function AlertsPage() {
  return (
    <MockStatPage<AlertRow>
      title="Cảnh báo"
      stats={[{ title: "Cảnh báo mới", value: 18 }]}
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Tiêu đề cảnh báo", dataIndex: "title" },
        { title: "Loại cảnh báo", dataIndex: "type" },
        {
          title: "Mức độ",
          dataIndex: "level",
          render: (level: AlertRow["level"]) => <Tag color={levelColor[level]}>{level}</Tag>,
        },
        { title: "Thời gian tạo", dataIndex: "createdAt" },
      ]}
    />
  );
}
