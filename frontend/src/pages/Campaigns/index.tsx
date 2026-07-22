import { useEffect, useState } from 'react'
import { Button, Card, Input, Select, Space, Table, Tag } from 'antd'
import { PlusOutlined, SearchOutlined, EyeOutlined, EditOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import StatusTag from '@/components/common/StatusTag'
import PageHeader from '@/components/common/PageHeader'
import { authFetch } from '@/lib/api'
import dayjs from 'dayjs'

type CampaignRow = {
  campaign_id: string
  code: string | null
  name: string
  status: string
  start_date: string
  end_date: string | null
  source_ids: string[]
  keyword_ids: string[]
}

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
  const [data, setData] = useState<CampaignRow[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<string>('')

  useEffect(() => {
    setIsLoading(true)
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    if (keyword) params.set('keyword', keyword)
    authFetch(`/api/campaigns?${params.toString()}`)
      .then((r) => (r.ok ? r.json() : { campaigns: [] }))
      .then((d) => setData(d.campaigns ?? []))
      .finally(() => setIsLoading(false))
  }, [status, keyword])

  const columns = [
    { title: 'Mã', dataIndex: 'code', key: 'code', width: 120, render: (v: string | null) => (v ? <Tag>{v}</Tag> : '—') },
    {
      title: 'Tên chiến dịch',
      dataIndex: 'name',
      key: 'name',
      render: (v: string, r: CampaignRow) => (
        <a onClick={() => navigate(`/campaigns/${r.campaign_id}`)} style={{ color: '#0B1F3A', fontWeight: 500 }}>
          {v}
        </a>
      ),
    },
    { title: 'Trạng thái', dataIndex: 'status', key: 'status', render: (v: string) => <StatusTag type="campaign" value={v} /> },
    { title: 'Số nguồn', render: (_: unknown, r: CampaignRow) => r.source_ids.length },
    { title: 'Số từ khóa', render: (_: unknown, r: CampaignRow) => r.keyword_ids.length },
    { title: 'Ngày bắt đầu', dataIndex: 'start_date', render: (v: string) => (v ? dayjs(v).format('DD/MM/YYYY') : '—') },
    { title: 'Ngày kết thúc', dataIndex: 'end_date', render: (v: string | null) => (v ? dayjs(v).format('DD/MM/YYYY') : '—') },
    {
      title: 'Thao tác',
      key: 'actions',
      width: 120,
      render: (_: unknown, r: CampaignRow) => (
        <Space>
          <Button type="text" icon={<EyeOutlined />} onClick={() => navigate(`/campaigns/${r.campaign_id}`)} />
          <Button type="text" icon={<EditOutlined />} onClick={() => navigate(`/campaigns/${r.campaign_id}/edit`)} />
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
          <Select value={status} onChange={(v) => setStatus(v)} options={STATUS_OPTIONS} style={{ width: 180 }} />
        </Space>

        <Table
          columns={columns}
          dataSource={data}
          rowKey="campaign_id"
          loading={isLoading}
          pagination={{ pageSize: 20, showTotal: (t) => `Tổng ${t} chiến dịch` }}
        />
      </Card>
    </div>
  )
}
