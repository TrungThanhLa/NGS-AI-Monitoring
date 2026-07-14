"use client";

import MockStatPage from "@/components/mock/MockStatPage";

type RuleRow = {
  id: string;
  name: string;
  condition: string;
  level: string;
};

const data: RuleRow[] = [
  { id: "1", name: "Từ khóa tăng đột biến", condition: "Tăng > 200% trong 1 giờ", level: "Rất cao" },
  { id: "2", name: "Sentiment tiêu cực tăng nhanh", condition: "Tỉ lệ tiêu cực > 60%", level: "Cao" },
];

export default function AlertRulesPage() {
  return (
    <MockStatPage<RuleRow>
      title="Cấu hình cảnh báo"
      description="Trang này chỉ minh hoạ giao diện — hệ thống chưa có cơ chế cấu hình cảnh báo thật."
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Tên quy tắc", dataIndex: "name" },
        { title: "Điều kiện", dataIndex: "condition" },
        { title: "Mức độ", dataIndex: "level" },
      ]}
    />
  );
}
