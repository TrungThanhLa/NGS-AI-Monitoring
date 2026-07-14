"use client";

import { useState } from "react";
import { Card, Col, Row, Statistic, Segmented, Typography } from "antd";
import {
  FileTextOutlined,
  GlobalOutlined,
  WarningOutlined,
  FolderOutlined,
  RiseOutlined,
  RightOutlined,
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

const { Text } = Typography;

type StatCard = {
  title: string;
  value: number;
  icon: React.ReactNode;
  iconBg: string;
  changeText: string;
  changeColor: string;
};

const statCards: StatCard[] = [
  {
    title: "Tổng số nội dung",
    value: 128456,
    icon: <FileTextOutlined />,
    iconBg: "#2E6FF2",
    changeText: "↑ 18,6% so với kỳ trước",
    changeColor: "#10B981",
  },
  {
    title: "Nội dung hôm nay",
    value: 2845,
    icon: <GlobalOutlined />,
    iconBg: "#10B981",
    changeText: "↑ 12,4% so với hôm qua",
    changeColor: "#10B981",
  },
  {
    title: "Cảnh báo mới",
    value: 18,
    icon: <WarningOutlined />,
    iconBg: "#EF4444",
    changeText: "↑ 5 cảnh báo",
    changeColor: "#EF4444",
  },
  {
    title: "Vụ việc đang xử lý",
    value: 27,
    icon: <FolderOutlined />,
    iconBg: "#14B8A6",
    changeText: "— Không thay đổi",
    changeColor: "#94A3B8",
  },
  {
    title: "Mức độ quan tâm cao",
    value: 156,
    icon: <RiseOutlined />,
    iconBg: "#2E6FF2",
    changeText: "↑ 22,1% so với kỳ trước",
    changeColor: "#10B981",
  },
];

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
  { name: "Facebook", value: 58246, percent: 45.3, color: "#2E6FF2" },
  { name: "Website", value: 28461, percent: 22.1, color: "#10B981" },
  { name: "TikTok", value: 20314, percent: 15.8, color: "#7C6EF0" },
  { name: "YouTube", value: 15872, percent: 12.4, color: "#94A3B8" },
  { name: "Zalo", value: 5563, percent: 4.3, color: "#14B8A6" },
];

const totalContent = platformData.reduce((s, p) => s + p.value, 0);

const topTopics = [
  { name: "Tin giả và thông tin sai lệch", count: 32456, percent: 25.2 },
  { name: "Lừa đảo, giả mạo", count: 25189, percent: 19.6 },
  { name: "Giải thích chính sách", count: 18742, percent: 14.6 },
];

const topKeywords = [
  { name: "deepfake", count: 12845, changePercent: 245 },
  { name: "lừa đảo online", count: 11265, changePercent: 180 },
  { name: "giả mạo cơ quan", count: 9842, changePercent: 165 },
];

const latestAlerts = [
  {
    level: "Rất cao",
    text: 'Từ khóa "deepfake" tăng đột biến 350%',
    time: "10:23",
    color: "#EF4444",
    bg: "#FEF2F2",
  },
  {
    level: "Cao",
    text: "Xuất hiện thông tin giả mạo Bộ Công an",
    time: "09:41",
    color: "#F97316",
    bg: "#FFF7ED",
  },
  {
    level: "Trung bình",
    text: "Nhiều bài viết tiêu cực về chính sách mới",
    time: "08:55",
    color: "#EAB308",
    bg: "#FEFCE8",
  },
];

function ViewAllLink({ text }: { text: string }) {
  return (
    <a style={{ fontSize: 13, color: "#2E6FF2", display: "inline-flex", alignItems: "center", gap: 4 }}>
      {text} <RightOutlined style={{ fontSize: 11 }} />
    </a>
  );
}

export default function DashboardPage() {
  const [range, setRange] = useState("Ngày");

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 20 }}>
        {statCards.map((s) => (
          <Col span={24 / statCards.length} key={s.title}>
            <Card styles={{ body: { padding: 20 } }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 10,
                    background: s.iconBg,
                    color: "#fff",
                    fontSize: 20,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  {s.icon}
                </div>
                <div style={{ minWidth: 0 }}>
                  <Text type="secondary" style={{ fontSize: 13 }}>
                    {s.title}
                  </Text>
                  <Statistic value={s.value} styles={{ content: { fontSize: 24, fontWeight: 700, lineHeight: 1.3 } }} />
                  <Text style={{ fontSize: 12, color: s.changeColor }}>{s.changeText}</Text>
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col span={16}>
          <Card
            title="Diễn biến số lượng nội dung theo thời gian"
            extra={<Segmented value={range} onChange={(v) => setRange(String(v))} options={["Ngày", "Tuần", "Tháng"]} />}
          >
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={trendData}>
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#2E6FF2" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col span={8}>
          <Card title="Nội dung theo nền tảng">
            <div style={{ position: "relative" }}>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={platformData} dataKey="value" nameKey="name" innerRadius={62} outerRadius={92} paddingAngle={1}>
                    {platformData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div
                style={{
                  position: "absolute",
                  top: "50%",
                  left: "50%",
                  transform: "translate(-50%, -58%)",
                  textAlign: "center",
                }}
              >
                <div style={{ fontSize: 20, fontWeight: 700 }}>{totalContent.toLocaleString("vi-VN")}</div>
                <div style={{ fontSize: 11, color: "#94A3B8" }}>Tổng số</div>
              </div>
            </div>
            <div style={{ marginTop: 8 }}>
              {platformData.map((p) => (
                <div
                  key={p.name}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 12.5,
                    padding: "4px 0",
                  }}
                >
                  <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: p.color, display: "inline-block" }} />
                    {p.name}
                  </span>
                  <span style={{ color: "#94A3B8" }}>
                    {p.value.toLocaleString("vi-VN")} ({p.percent}%)
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={8}>
          <Card
            title="Top chủ đề nổi bật"
            extra={<ViewAllLink text="Xem tất cả" />}
            styles={{ body: { paddingTop: 8 } }}
          >
            {topTopics.map((t, i) => (
              <div key={t.name} style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span
                    style={{
                      width: 20,
                      height: 20,
                      borderRadius: "50%",
                      background: "#2E6FF2",
                      color: "#fff",
                      fontSize: 11,
                      fontWeight: 600,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    {i + 1}
                  </span>
                  <Text style={{ fontSize: 13, flex: 1 }}>{t.name}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {t.count.toLocaleString("vi-VN")} ({t.percent}%)
                  </Text>
                </div>
                <div style={{ height: 6, background: "#F1F5F9", borderRadius: 4, marginLeft: 28 }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${t.percent * 3}%`,
                      background: "#2E6FF2",
                      borderRadius: 4,
                    }}
                  />
                </div>
              </div>
            ))}
          </Card>
        </Col>
        <Col span={8}>
          <Card title="Top từ khóa nóng" extra={<ViewAllLink text="Xem tất cả" />} styles={{ body: { paddingTop: 8 } }}>
            {topKeywords.map((k, i) => (
              <div
                key={k.name}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "10px 0",
                  borderBottom: i < topKeywords.length - 1 ? "1px solid #f0f0f0" : "none",
                }}
              >
                <Text style={{ fontSize: 13 }}>
                  {i + 1}. {k.name}
                </Text>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{k.count.toLocaleString("vi-VN")}</div>
                  <div style={{ fontSize: 11.5, color: "#EF4444" }}>↑ {k.changePercent}%</div>
                </div>
              </div>
            ))}
          </Card>
        </Col>
        <Col span={8}>
          <Card title="Cảnh báo mới nhất" extra={<ViewAllLink text="Xem tất cả" />} styles={{ body: { paddingTop: 8 } }}>
            {latestAlerts.map((a) => (
              <div key={a.text} style={{ display: "flex", gap: 10, marginBottom: 14 }}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: a.color,
                    background: a.bg,
                    padding: "2px 8px",
                    borderRadius: 4,
                    height: "fit-content",
                    whiteSpace: "nowrap",
                  }}
                >
                  {a.level.toUpperCase()}
                </span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13 }}>{a.text}</div>
                  <Text type="secondary" style={{ fontSize: 11.5 }}>
                    {a.time}
                  </Text>
                </div>
              </div>
            ))}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
