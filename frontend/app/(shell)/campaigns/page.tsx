"use client";

import { Tag } from "antd";
import MockStatPage from "@/components/mock/MockStatPage";

type Campaign = {
  id: string;
  code: string;
  name: string;
  owner: string;
  status: "Đang chạy" | "Tạm dừng" | "Nháp";
  sourceCount: number;
  contentCount: number;
};

const data: Campaign[] = [
  { id: "1", code: "CD001", name: "Giám sát tin giả Quý 3", owner: "Nguyễn Văn A", status: "Đang chạy", sourceCount: 7, contentCount: 1284 },
  { id: "2", code: "CD002", name: "Giám sát lừa đảo trực tuyến", owner: "Trần Thị B", status: "Đang chạy", sourceCount: 5, contentCount: 852 },
  { id: "3", code: "CD003", name: "Giám sát Deepfake", owner: "Lê Văn C", status: "Tạm dừng", sourceCount: 3, contentCount: 210 },
];

const statusColor: Record<Campaign["status"], string> = {
  "Đang chạy": "green",
  "Tạm dừng": "orange",
  "Nháp": "default",
};

export default function CampaignsPage() {
  return (
    <MockStatPage<Campaign>
      title="Chiến dịch giám sát"
      stats={[
        { title: "Tổng chiến dịch", value: data.length },
        { title: "Đang chạy", value: data.filter((c) => c.status === "Đang chạy").length },
        { title: "Tổng nội dung", value: data.reduce((s, c) => s + c.contentCount, 0) },
      ]}
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Mã", dataIndex: "code" },
        { title: "Tên chiến dịch", dataIndex: "name" },
        { title: "Người phụ trách", dataIndex: "owner" },
        { title: "Số nguồn", dataIndex: "sourceCount" },
        { title: "Số nội dung", dataIndex: "contentCount" },
        {
          title: "Trạng thái",
          dataIndex: "status",
          render: (status: Campaign["status"]) => <Tag color={statusColor[status]}>{status}</Tag>,
        },
      ]}
    />
  );
}
