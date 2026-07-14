"use client";

import { Tag } from "antd";
import MockStatPage from "@/components/mock/MockStatPage";

type ContentRow = {
  id: string;
  title: string;
  source: string;
  platform: string;
  publishedAt: string;
  sentiment: "Tích cực" | "Trung tính" | "Tiêu cực";
};

const data: ContentRow[] = [
  { id: "1", title: "Cảnh báo chiêu trò giả mạo ngân hàng", source: "VTV News", platform: "Website", publishedAt: "14/07/2026", sentiment: "Tiêu cực" },
  { id: "2", title: "Hướng dẫn nhận diện tin giả trên mạng xã hội", source: "VOV", platform: "Website", publishedAt: "13/07/2026", sentiment: "Tích cực" },
  { id: "3", title: "Thông tin chính sách mới về an toàn thông tin", source: "CAND", platform: "Website", publishedAt: "12/07/2026", sentiment: "Trung tính" },
];

const sentimentColor: Record<ContentRow["sentiment"], string> = {
  "Tích cực": "green",
  "Trung tính": "default",
  "Tiêu cực": "red",
};

export default function ContentsPage() {
  return (
    <MockStatPage<ContentRow>
      title="Nội dung thu thập"
      stats={[
        { title: "Tổng nội dung", value: 128456 },
        { title: "Hôm nay", value: 2845 },
      ]}
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Tiêu đề", dataIndex: "title" },
        { title: "Nguồn", dataIndex: "source" },
        { title: "Nền tảng", dataIndex: "platform" },
        { title: "Thời gian đăng", dataIndex: "publishedAt" },
        {
          title: "Sentiment",
          dataIndex: "sentiment",
          render: (s: ContentRow["sentiment"]) => <Tag color={sentimentColor[s]}>{s}</Tag>,
        },
      ]}
    />
  );
}
