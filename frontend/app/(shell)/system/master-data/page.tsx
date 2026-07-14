"use client";

import { Tag } from "antd";
import MockStatPage from "@/components/mock/MockStatPage";

type Topic = {
  id: string;
  code: string;
  name: string;
  status: "Đang sử dụng" | "Tạm ngưng";
};

const data: Topic[] = [
  { id: "1", code: "TOPIC_01", name: "Tin giả và thông tin sai lệch", status: "Đang sử dụng" },
  { id: "2", code: "TOPIC_02", name: "Phản bác, đính chính thông tin", status: "Đang sử dụng" },
  { id: "3", code: "TOPIC_03", name: "Kiểm chứng và xác thực thông tin", status: "Đang sử dụng" },
  { id: "4", code: "TOPIC_04", name: "Giải thích chính sách và cung cấp thông tin chính thống", status: "Đang sử dụng" },
  { id: "5", code: "TOPIC_05", name: "Cảnh báo lừa đảo, giả mạo trên không gian mạng", status: "Đang sử dụng" },
  { id: "6", code: "TOPIC_06", name: "AI, Deepfake và công nghệ tạo sinh", status: "Đang sử dụng" },
  { id: "7", code: "TOPIC_07", name: "An toàn thông tin và an ninh mạng", status: "Đang sử dụng" },
  { id: "8", code: "TOPIC_08", name: "Hướng dẫn nhận diện tin giả và nâng cao kỹ năng truyền thông số", status: "Đang sử dụng" },
];

export default function MasterDataPage() {
  return (
    <MockStatPage<Topic>
      title="Dữ liệu dùng chung — Chủ đề"
      description="Danh mục 8 nhóm chủ đề dùng cho phân loại AI (backend/ai/prompts/v1.py). Trang này chỉ minh hoạ giao diện, chưa CRUD thật."
      stats={[{ title: "Tổng số chủ đề", value: data.length }]}
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Mã", dataIndex: "code" },
        { title: "Tên chủ đề", dataIndex: "name" },
        {
          title: "Trạng thái",
          dataIndex: "status",
          render: (s: Topic["status"]) => <Tag color={s === "Đang sử dụng" ? "green" : "default"}>{s}</Tag>,
        },
      ]}
    />
  );
}
