"use client";

import { Tag } from "antd";
import MockStatPage from "@/components/mock/MockStatPage";

type UserRow = {
  id: string;
  name: string;
  username: string;
  email: string;
  role: string;
  status: "Hoạt động" | "Khoá";
};

const data: UserRow[] = [
  { id: "1", name: "Nguyễn Văn A", username: "vana", email: "vana@ngsmonitor.vn", role: "Admin", status: "Hoạt động" },
  { id: "2", name: "Trần Thị B", username: "thib", email: "thib@ngsmonitor.vn", role: "Analyst", status: "Hoạt động" },
];

export default function UsersPage() {
  return (
    <MockStatPage<UserRow>
      title="Người dùng & phân quyền"
      description="Hệ thống hiện tại chưa có auth/RBAC thật — trang này chỉ minh hoạ giao diện."
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Họ tên", dataIndex: "name" },
        { title: "Tên đăng nhập", dataIndex: "username" },
        { title: "Email", dataIndex: "email" },
        { title: "Nhóm quyền", dataIndex: "role" },
        {
          title: "Trạng thái",
          dataIndex: "status",
          render: (s: UserRow["status"]) => <Tag color={s === "Hoạt động" ? "green" : "red"}>{s}</Tag>,
        },
      ]}
    />
  );
}
