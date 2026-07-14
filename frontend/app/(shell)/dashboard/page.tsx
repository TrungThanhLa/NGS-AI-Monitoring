"use client";

import { Card, Col, Row, Statistic, List, Tag } from "antd";
import {
  FileTextOutlined,
  GlobalOutlined,
  WarningOutlined,
  FolderOutlined,
  RiseOutlined,
} from "@ant-design/icons";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const trendData = [
  { date: "01/01", value: 3200 },
  { date: "15/01", value: 4100 },
  { date: "29/01", value: 3800 },
  { date: "12/02", value: 5200 },
  { date: "26/02", value: 4600 },
  { date: "12/03", value: 5100 },
  { date: "26/03", value: 6842 },
  { date: "09/04", value: 6100 },
];

const platformData = [
  { name: "Facebook", value: 58246 },
  { name: "Website", value: 28461 },
  { name: "TikTok", value: 20314 },
  { name: "YouTube", value: 15872 },
  { name: "Zalo", value: 5563 },
];

const platformColors = ["#0A5CC2", "#10B981", "#6366F1", "#94A3B8", "#F59E0B"];

const topTopics = [
  { name: "Tin giả và thông tin sai lệch", percent: 25.2 },
  { name: "Lừa đảo, giả mạo", percent: 19.6 },
  { name: "Giải thích chính sách", percent: 14.6 },
];

const latestAlerts = [
  { level: "Rất cao", text: 'Từ khóa "deepfake" tăng đột biến 350%' },
  { level: "Cao", text: "Xuất hiện thông tin giả mạo Bộ Công an" },
  { level: "Trung bình", text: "Nhiều bài viết tiêu cực về chính sách mới" },
];

const levelColor: Record<string, string> = {
  "Rất cao": "red",
  "Cao": "orange",
  "Trung bình": "gold",
};

export default function DashboardPage() {
  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={5}>
          <Card>
            <Statistic title="Tổng số nội dung" value={128456} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="Nội dung hôm nay" value={2845} prefix={<GlobalOutlined />} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="Cảnh báo mới" value={18} prefix={<WarningOutlined />} valueStyle={{ color: "#cf1322" }} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="Vụ việc đang xử lý" value={27} prefix={<FolderOutlined />} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="Mức độ quan tâm cao" value={156} prefix={<RiseOutlined />} />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={16}>
          <Card title="Diễn biến số lượng nội dung theo thời gian">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={trendData}>
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#0A5CC2" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col span={8}>
          <Card title="Nội dung theo nền tảng">
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={platformData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={90}>
                  {platformData.map((entry, index) => (
                    <Cell key={entry.name} fill={platformColors[index % platformColors.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="Top chủ đề nổi bật">
            <List
              dataSource={topTopics}
              renderItem={(item) => (
                <List.Item>
                  {item.name} — {item.percent}%
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Cảnh báo mới nhất">
            <List
              dataSource={latestAlerts}
              renderItem={(item) => (
                <List.Item>
                  <Tag color={levelColor[item.level]}>{item.level}</Tag> {item.text}
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
