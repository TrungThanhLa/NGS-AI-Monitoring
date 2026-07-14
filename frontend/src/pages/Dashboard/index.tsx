import { Col, Row, Card, Statistic, Table, Tag, Typography } from 'antd'
import {
  FileTextOutlined,
  WarningOutlined,
  SafetyCertificateOutlined,
  RadarChartOutlined,
  ArrowUpOutlined,
} from '@ant-design/icons'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  Legend,
} from 'recharts'
import { COLORS } from '@/theme'
import SeverityTag from '@/components/common/SeverityTag'
import StatusTag from '@/components/common/StatusTag'
import PageHeader from '@/components/common/PageHeader'

const trendData = [
  { date: '10/06', count: 45 },
  { date: '11/06', count: 72 },
  { date: '12/06', count: 58 },
  { date: '13/06', count: 91 },
  { date: '14/06', count: 67 },
  { date: '15/06', count: 84 },
  { date: '16/06', count: 103 },
  { date: '17/06', count: 88 },
  { date: '18/06', count: 115 },
]

const sentimentData = [
  { name: 'Tiêu cực', value: 38 },
  { name: 'Trung lập', value: 45 },
  { name: 'Tích cực', value: 17 },
]

const platformData = [
  { platform: 'Facebook', count: 320 },
  { platform: 'Website', count: 215 },
  { platform: 'YouTube', count: 87 },
  { platform: 'TikTok', count: 143 },
  { platform: 'RSS', count: 56 },
]

const keywordsData = [
  { keyword: 'chính sách', count: 142 },
  { keyword: 'giá cả', count: 98 },
  { keyword: 'dự án', count: 76 },
  { keyword: 'phản đối', count: 54 },
  { keyword: 'ủng hộ', count: 43 },
]

const recentAlerts = [
  { id: '1', title: 'Nội dung tiêu cực về dự án X', severity: 'CRITICAL', status: 'NEW', created_at: '2026-06-18 09:15' },
  { id: '2', title: 'Tăng đột biến nhắc đến từ khóa "phản đối"', severity: 'HIGH', status: 'ACKNOWLEDGED', created_at: '2026-06-18 08:42' },
  { id: '3', title: 'Bài viết viral về chính sách mới', severity: 'MEDIUM', status: 'PROCESSING', created_at: '2026-06-17 22:10' },
]

const kpiCards = [
  { title: 'Nội dung mới hôm nay', value: 115, icon: <FileTextOutlined />, color: '#0B1F3A', suffix: '+12%' },
  { title: 'Cảnh báo khẩn cấp', value: 8, icon: <WarningOutlined />, color: '#F5222D', suffix: '+3' },
  { title: 'Vụ việc đang mở', value: 14, icon: <SafetyCertificateOutlined />, color: '#FA8C16', suffix: '' },
  { title: 'Chiến dịch đang chạy', value: 6, icon: <RadarChartOutlined />, color: '#009688', suffix: '' },
]

export default function DashboardPage() {
  return (
    <div>
      <PageHeader title="Tổng quan" subtitle="Theo dõi tình hình giám sát thông tin" />

      <Row gutter={[16, 16]}>
        {kpiCards.map((card) => (
          <Col xs={24} sm={12} lg={6} key={card.title}>
            <Card
              style={{
                borderRadius: 12,
                height: 120,
                boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                borderLeft: `4px solid ${card.color}`,
              }}
              styles={{ body: { padding: '16px 20px', height: '100%', display: 'flex', alignItems: 'center', gap: 16 } }}
            >
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 12,
                  background: card.color + '15',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 22,
                  color: card.color,
                  flexShrink: 0,
                }}
              >
                {card.icon}
              </div>
              <div>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {card.title}
                </Typography.Text>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                  <Typography.Title level={3} style={{ margin: 0, color: '#0B1F3A' }}>
                    {card.value}
                  </Typography.Title>
                  {card.suffix && (
                    <Typography.Text style={{ color: '#52C41A', fontSize: 12, fontWeight: 500 }}>
                      <ArrowUpOutlined /> {card.suffix}
                    </Typography.Text>
                  )}
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={16}>
          <Card title="Xu hướng nội dung (7 ngày)" style={{ borderRadius: 12 }}>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={trendData}>
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke="#009688" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="Phân bổ cảm xúc" style={{ borderRadius: 12 }}>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={sentimentData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                  {sentimentData.map((_, i) => (
                    <Cell key={i} fill={[COLORS.error, '#8C8C8C', COLORS.success][i]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="Nội dung theo nền tảng" style={{ borderRadius: 12 }}>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={platformData} layout="vertical">
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis dataKey="platform" type="category" tick={{ fontSize: 12 }} width={70} />
                <Tooltip />
                <Bar dataKey="count" fill="#0B1F3A" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="Từ khóa nổi bật" style={{ borderRadius: 12 }}>
            <Table
              dataSource={keywordsData}
              rowKey="keyword"
              pagination={false}
              size="small"
              columns={[
                { title: 'Từ khóa', dataIndex: 'keyword', key: 'keyword' },
                {
                  title: 'Số lần nhắc',
                  dataIndex: 'count',
                  key: 'count',
                  align: 'right',
                  render: (v) => <Tag color="blue">{v}</Tag>,
                },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Row style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card title="Cảnh báo gần đây" style={{ borderRadius: 12 }}>
            <Table
              dataSource={recentAlerts}
              rowKey="id"
              pagination={false}
              size="small"
              columns={[
                { title: 'Tiêu đề', dataIndex: 'title', key: 'title' },
                {
                  title: 'Mức độ',
                  dataIndex: 'severity',
                  key: 'severity',
                  render: (v) => <SeverityTag value={v} />,
                },
                {
                  title: 'Trạng thái',
                  dataIndex: 'status',
                  key: 'status',
                  render: (v) => <StatusTag type="alert" value={v} />,
                },
                { title: 'Thời gian', dataIndex: 'created_at', key: 'created_at' },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
