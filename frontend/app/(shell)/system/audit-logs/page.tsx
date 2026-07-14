"use client";

import MockStatPage from "@/components/mock/MockStatPage";

type LogRow = {
  id: string;
  user: string;
  action: string;
  object: string;
  time: string;
};

const data: LogRow[] = [
  { id: "1", user: "Nguyễn Văn A", action: "Tạo báo cáo", object: "JOB-0231", time: "14/07/2026 08:00" },
  { id: "2", user: "Trần Thị B", action: "Đăng nhập", object: "-", time: "14/07/2026 07:50" },
];

export default function AuditLogsPage() {
  return (
    <MockStatPage<LogRow>
      title="Nhật ký hệ thống"
      description="Trang này chỉ minh hoạ giao diện — hệ thống chưa ghi audit log thật."
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Người dùng", dataIndex: "user" },
        { title: "Hành động", dataIndex: "action" },
        { title: "Đối tượng", dataIndex: "object" },
        { title: "Thời gian", dataIndex: "time" },
      ]}
    />
  );
}
