"use client";

import { Tag } from "antd";
import MockStatPage from "@/components/mock/MockStatPage";

type CaseRow = {
  id: string;
  code: string;
  name: string;
  priority: "Thấp" | "Trung bình" | "Cao";
  status: "Mới phát hiện" | "Đang xác minh" | "Đang xử lý" | "Đã xử lý";
  owner: string;
};

const data: CaseRow[] = [
  { id: "1", code: "VV001", name: "Giả mạo website dịch vụ công trực tuyến", priority: "Cao", status: "Đang xử lý", owner: "Nguyễn Văn A" },
  { id: "2", code: "VV002", name: "Lừa đảo tuyển dụng qua mạng xã hội", priority: "Trung bình", status: "Đang xác minh", owner: "Trần Thị B" },
];

const statusColor: Record<CaseRow["status"], string> = {
  "Mới phát hiện": "default",
  "Đang xác minh": "gold",
  "Đang xử lý": "blue",
  "Đã xử lý": "green",
};

export default function CasesPage() {
  return (
    <MockStatPage<CaseRow>
      title="Vụ việc"
      stats={[{ title: "Vụ việc đang xử lý", value: 27 }]}
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Mã vụ việc", dataIndex: "code" },
        { title: "Tên vụ việc", dataIndex: "name" },
        { title: "Người phụ trách", dataIndex: "owner" },
        {
          title: "Trạng thái",
          dataIndex: "status",
          render: (s: CaseRow["status"]) => <Tag color={statusColor[s]}>{s}</Tag>,
        },
      ]}
    />
  );
}
