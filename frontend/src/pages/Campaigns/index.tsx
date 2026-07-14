import { useState } from 'react'
import { Button, Card, Input, Select, Space, Table, Tag } from 'antd'
import { PlusOutlined, SearchOutlined, EyeOutlined, EditOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { campaigns as mockCampaigns } from '@/data/mockData'
import StatusTag from '@/components/common/StatusTag'
import PageHeader from '@/components/common/PageHeader'
import dayjs from 'dayjs'

const STATUS_OPTIONS = [
  { value: '', label: 'Tất cả trạng thái' },
  { value: 'DRAFT', label: 'Nháp' },
  { value: 'ACTIVE', label: 'Đang hoạt động' },
  { value: 'PAUSED', label: 'Tạm dừng' },
  { value: 'COMPLETED', label: 'Hoàn thành' },
  { value: 'ARCHIVED', label: 'Lưu trữ' },
]

export default function CampaignsPage() {
  const navigate = useNavigate()
  const [data] = useState(mockCampaigns)
  const isLoading = false
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<string>('')

  const filtered = data.filter(
    (c) =>
      (!keyword || c.name.toLowerCase().includes(keyword.toLowerCase())) &&
      (!status || c.status === status),
  )

  const columns = [
    { title: 'Mã', dataIndex: 'code', key: 'code', width: 120, render: (v: string) => <Tag>{v}</Tag> },
    {
      title: 'Tên chiến dịch',
      dataIndex: 'name',
      key: 'name',
      render: (v: string, r: { id: string }) => (
        <a onClick={() => navigate(`/campaigns/${r.id}`)} style={{ color: '#0B1F3A', fontWeight: 500 }}>
          {v}
        </a>
      ),
    },
    {
      title: 'Trạng thái',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => <StatusTag type="campaign" value={v} />,
    },
    { title: 'Người tạo', dataIndex: 'owner_name', key: 'owner_name' },
    {
      title: 'Ngày bắt đầu',
      dataIndex: 'start_date',
      key: 'start_date',
      render: (v: string) => (v ? dayjs(v).format('DD/MM/YYYY') : '—'),
    },
    {
      title: 'Ngày kết thúc',
      dataIndex: 'end_date',
      key: 'end_date',
      render: (v: string) => (v ? dayjs(v).format('DD/MM/YYYY') : '—'),
    },
    {
      title: 'Thao tác',
      key: 'actions',
      width: 120,
      render: (_: unknown, r: { id: string }) => (
        <Space>
          <Button type="text" icon={<EyeOutlined />} onClick={() => navigate(`/campaigns/${r.id}`)} />
          <Button type="text" icon={<EditOutlined />} onClick={() => navigate(`/campaigns/${r.id}/edit`)} />
        </Space>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title="Chiến dịch giám sát"
        subtitle="Quản lý các chiến dịch giám sát thông tin"
        breadcrumbs={[{ title: 'Tổng quan', href: '/' }, { title: 'Chiến dịch giám sát' }]}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/campaigns/new')}>
            Tạo chiến dịch
          </Button>
        }
      />

      <Card style={{ borderRadius: 12 }}>
        <Space style={{ marginBottom: 16 }}>
          <Input
            placeholder="Tìm kiếm chiến dịch..."
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 280 }}
            allowClear
          />
          <Select
            value={status}
            onChange={(v) => setStatus(v)}
            options={STATUS_OPTIONS}
            style={{ width: 180 }}
          />
        </Space>

        <Table
          columns={columns}
          dataSource={filtered}
          rowKey="id"
          loading={isLoading}
          pagination={{
            pageSize: 20,
            showTotal: (t) => `Tổng ${t} chiến dịch`,
          }}
        />
      </Card>
    </div>
  )
}
