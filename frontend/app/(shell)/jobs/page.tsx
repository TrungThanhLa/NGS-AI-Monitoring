"use client";

import { Tag } from "antd";
import MockStatPage from "@/components/mock/MockStatPage";

type JobRow = {
  id: string;
  code: string;
  type: "Crawl" | "AI" | "Report";
  source: string;
  status: "Đang chạy" | "Hoàn thành" | "Lỗi";
  startedAt: string;
};

const data: JobRow[] = [
  { id: "1", code: "JOB-0231", type: "Crawl", source: "VTV News", status: "Hoàn thành", startedAt: "14/07/2026 08:00" },
  { id: "2", code: "JOB-0232", type: "AI", source: "VOV", status: "Đang chạy", startedAt: "14/07/2026 09:10" },
];

const statusColor: Record<JobRow["status"], string> = {
  "Đang chạy": "blue",
  "Hoàn thành": "green",
  "Lỗi": "red",
};

export default function JobsPage() {
  return (
    <MockStatPage<JobRow>
      title="Lịch chạy & Jobs"
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Mã Job", dataIndex: "code" },
        { title: "Loại Job", dataIndex: "type" },
        { title: "Nguồn", dataIndex: "source" },
        {
          title: "Trạng thái",
          dataIndex: "status",
          render: (s: JobRow["status"]) => <Tag color={statusColor[s]}>{s}</Tag>,
        },
        { title: "Bắt đầu", dataIndex: "startedAt" },
      ]}
    />
  );
}
