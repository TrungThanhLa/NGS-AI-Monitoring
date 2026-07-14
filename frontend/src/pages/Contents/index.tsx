import { useState } from 'react'
import { Button, Card, DatePicker, Input, Select, Space, Table } from 'antd'
import { SearchOutlined, EyeOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { contents as mockContents } from '@/data/mockData'
import StatusTag from '@/components/common/StatusTag'
import SeverityTag from '@/components/common/SeverityTag'
import PageHeader from '@/components/common/PageHeader'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

type Content = (typeof mockContents)[number]

export default function ContentsPage() {
  const navigate = useNavigate()
  const [data] = useState(mockContents)
  const isLoading = false
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState('')
  const [sentiment, setSentiment] = useState('')
  const [attentionLevel, setAttentionLevel] = useState('')
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null)

  const filtered = data.filter(
    (c) =>
      (!keyword || c.title.toLowerCase().includes(keyword.toLowerCase())) &&
      (!status || c.status === status) &&
      (!sentiment || c.sentiment === sentiment) &&
      (!attentionLevel || c.attention_level === attentionLevel) &&
      (!dateRange?.[0] || !dateRange?.[1] ||
        (dayjs(c.published_at).isAfter(dateRange[0].startOf('day')) &&
          dayjs(c.published_at).isBefore(dateRange[1].endOf('day')))),
  )

  const columns = [
    {
      title: 'Tiêu đề',
      dataIndex: 'title',
      key: 'title',
      render: (v: string, r: Content) => (
        <a onClick={() => navigate(`/contents/${r.id}`)} style={{ color: '#0B1F3A', fontWeight: 500 }}>
          {v}
        </a>
      ),
    },
    {
      title: 'Nguồn',
      key: 'source',
      render: (_: unknown, r: Content) => r.source?.name ?? '—',
    },
    {
      title: 'Cảm xúc',
      dataIndex: 'sentiment',
      key: 'sentiment',
      render: (v: string) => (v ? <StatusTag type="sentiment" value={v} /> : '—'),
    },
    {
      title: 'Mức độ chú ý',
      dataIndex: 'attention_level',
      key: 'attention_level',
      render: (v: string) => (v ? <SeverityTag type="attention" value={v} /> : '—'),
    },
    {
      title: 'Trạng thái',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => <StatusTag type="content" value={v} />,
    },
    {
      title: 'Ngày đăng',
      dataIndex: 'published_at',
      key: 'published_at',
      render: (v: string) => (v ? dayjs(v).format('DD/MM/YYYY') : '—'),
    },
    {
      title: '',
      key: 'action',
      width: 48,
      render: (_: unknown, r: Content) => (
        <Button type="text" icon={<EyeOutlined />} onClick={() => navigate(`/contents/${r.id}`)} />
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title="Nội dung"
        subtitle="Theo dõi và xem xét các nội dung thu thập được"
        breadcrumbs={[{ title: 'Tổng quan', href: '/' }, { title: 'Nội dung' }]}
      />

      <Card style={{ borderRadius: 12 }}>
        <Space wrap style={{ marginBottom: 16 }}>
          <Input
            placeholder="Tìm kiếm nội dung..."
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 260 }}
            allowClear
          />
          <Select
            value={status}
            onChange={(v) => setStatus(v)}
            options={[
              { value: '', label: 'Tất cả trạng thái' },
              { value: 'NEW', label: 'Mới' },
              { value: 'REVIEWED', label: 'Đã xem xét' },
              { value: 'NEED_VERIFY', label: 'Cần xác minh' },
              { value: 'VERIFIED', label: 'Đã xác minh' },
              { value: 'NOT_RELEVANT', label: 'Không liên quan' },
              { value: 'CASE_CREATED', label: 'Đã tạo vụ việc' },
            ]}
            style={{ width: 160 }}
          />
          <Select
            value={sentiment}
            onChange={(v) => setSentiment(v)}
            options={[
              { value: '', label: 'Tất cả cảm xúc' },
              { value: 'POSITIVE', label: 'Tích cực' },
              { value: 'NEGATIVE', label: 'Tiêu cực' },
              { value: 'NEUTRAL', label: 'Trung lập' },
              { value: 'MIXED', label: 'Hỗn hợp' },
            ]}
            style={{ width: 140 }}
          />
          <Select
            value={attentionLevel}
            onChange={(v) => setAttentionLevel(v)}
            options={[
              { value: '', label: 'Tất cả mức độ' },
              { value: 'LOW', label: 'Thấp' },
              { value: 'MEDIUM', label: 'Trung bình' },
              { value: 'HIGH', label: 'Cao' },
              { value: 'CRITICAL', label: 'Nguy hiểm' },
            ]}
            style={{ width: 140 }}
          />
          <RangePicker
            format="DD/MM/YYYY"
            onChange={(v) => setDateRange(v as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null)}
          />
        </Space>

        <Table
          columns={columns}
          dataSource={filtered}
          rowKey="id"
          loading={isLoading}
          pagination={{
            pageSize: 20,
            showTotal: (t) => `Tổng ${t} nội dung`,
          }}
        />
      </Card>
    </div>
  )
}
