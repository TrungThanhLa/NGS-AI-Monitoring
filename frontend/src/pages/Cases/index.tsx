import { useState } from 'react'
import { Button, Card, Input, Select, Space, Table } from 'antd'
import { PlusOutlined, SearchOutlined, EyeOutlined, EditOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { cases as mockCases } from '@/data/mockData'
import StatusTag from '@/components/common/StatusTag'
import SeverityTag from '@/components/common/SeverityTag'
import PageHeader from '@/components/common/PageHeader'
import dayjs from 'dayjs'

// Giá trị thật xuất hiện trong mockData.ts (cases): OPEN, INVESTIGATING, CONCLUDED — khớp với StatusTag.CASE_STATUS
const STATUS_OPTIONS = [
  { value: '', label: 'Tất cả trạng thái' },
  { value: 'OPEN', label: 'Mở' },
  { value: 'INVESTIGATING', label: 'Đang điều tra' },
  { value: 'CONCLUDED', label: 'Đã kết luận' },
]

// Giá trị thật xuất hiện trong mockData.ts (cases): HIGH, CRITICAL — khớp với SeverityTag.PRIORITY
const PRIORITY_OPTIONS = [
  { value: '', label: 'Tất cả ưu tiên' },
  { value: 'HIGH', label: 'Cao' },
  { value: 'CRITICAL', label: 'Khẩn cấp' },
]

export default function CasesPage() {
  const navigate = useNavigate()
  const [data] = useState(mockCases)
  const isLoading = false
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')

  const filtered = data.filter(
    (c) =>
      (!keyword ||
        c.title.toLowerCase().includes(keyword.toLowerCase()) ||
        c.code.toLowerCase().includes(keyword.toLowerCase())) &&
      (!status || c.status === status) &&
      (!priority || c.priority === priority),
  )

  const columns = [
    {
      title: 'Mã vụ việc',
      dataIndex: 'code',
      key: 'code',
      width: 160,
      render: (v: string, r: { id: string }) => (
        <a onClick={() => navigate(`/cases/${r.id}`)} style={{ fontWeight: 600, color: '#0B1F3A' }}>
          {v}
        </a>
      ),
    },
    { title: 'Tiêu đề', dataIndex: 'title', key: 'title' },
    {
      title: 'Ưu tiên',
      dataIndex: 'priority',
      key: 'priority',
      render: (v: string) => <SeverityTag type="priority" value={v} />,
    },
    {
      title: 'Trạng thái',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => <StatusTag type="case" value={v} />,
    },
    {
      title: 'Phụ trách',
      dataIndex: 'assigned_to',
      key: 'assigned_to',
      render: (v: { full_name: string } | null) => v?.full_name ?? '—',
    },
    {
      title: 'Ngày tạo',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => dayjs(v).format('DD/MM/YYYY'),
    },
    {
      title: 'Thao tác',
      key: 'actions',
      width: 120,
      render: (_: unknown, r: { id: string }) => (
        <Space>
          <Button type="text" icon={<EyeOutlined />} onClick={() => navigate(`/cases/${r.id}`)} />
          <Button type="text" icon={<EditOutlined />} onClick={() => navigate(`/cases/${r.id}/edit`)} />
        </Space>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title="Vụ việc"
        subtitle="Quản lý và theo dõi các vụ việc"
        breadcrumbs={[{ title: 'Tổng quan', href: '/' }, { title: 'Vụ việc' }]}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/cases/new')}>
            Tạo vụ việc
          </Button>
        }
      />

      <Card style={{ borderRadius: 12 }}>
        <Space style={{ marginBottom: 16 }}>
          <Input
            placeholder="Tìm kiếm vụ việc..."
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 260 }}
            allowClear
          />
          <Select value={status} onChange={setStatus} options={STATUS_OPTIONS} style={{ width: 180 }} />
          <Select value={priority} onChange={setPriority} options={PRIORITY_OPTIONS} style={{ width: 160 }} />
        </Space>

        <Table
          columns={columns}
          dataSource={filtered}
          rowKey="id"
          loading={isLoading}
          pagination={{ pageSize: 20, showTotal: (t) => `Tổng ${t} vụ việc` }}
        />
      </Card>
    </div>
  )
}
