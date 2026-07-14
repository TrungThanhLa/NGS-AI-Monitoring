import { useState } from 'react'
import { App, Button, Card, Select, Space, Table } from 'antd'
import { EyeOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { alerts as mockAlerts } from '@/data/mockData'
import StatusTag from '@/components/common/StatusTag'
import SeverityTag from '@/components/common/SeverityTag'
import PageHeader from '@/components/common/PageHeader'
import dayjs from 'dayjs'

type Alert = (typeof mockAlerts)[number]

export default function AlertsPage() {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const [data, setData] = useState(mockAlerts)
  const isLoading = false
  const [statusFilter, setStatusFilter] = useState('')
  const [severity, setSeverity] = useState('')

  const filtered = data.filter(
    (a) =>
      (!statusFilter || a.status === statusFilter) &&
      (!severity || a.severity === severity),
  )

  const acknowledge = (id: string) => {
    setData((prev) => prev.map((a) => (a.id === id ? { ...a, status: 'IN_PROGRESS' } : a)))
    message.info('Đây là giao diện minh hoạ — chưa lưu được thật')
  }

  const columns = [
    {
      title: 'Tiêu đề',
      dataIndex: 'title',
      key: 'title',
      render: (v: string, r: Alert) => (
        <a onClick={() => navigate(`/alerts/${r.id}`)} style={{ fontWeight: 500, color: '#0B1F3A' }}>
          {v}
        </a>
      ),
    },
    { title: 'Loại', dataIndex: 'alert_type', key: 'alert_type' },
    {
      title: 'Mức độ',
      dataIndex: 'severity',
      key: 'severity',
      render: (v: string) => <SeverityTag value={v} />,
    },
    {
      title: 'Trạng thái',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => <StatusTag type="alert" value={v} />,
    },
    {
      title: 'Nội dung liên quan',
      key: 'content',
      render: (_: unknown, r: Alert) => r.content_title ?? '—',
    },
    {
      title: 'Thời gian',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => dayjs(v).format('DD/MM/YYYY HH:mm'),
    },
    {
      title: 'Thao tác',
      key: 'actions',
      width: 100,
      render: (_: unknown, r: Alert) => (
        <Space>
          <Button type="text" icon={<EyeOutlined />} onClick={() => navigate(`/alerts/${r.id}`)} />
          {r.status === 'OPEN' && (
            <Button type="link" size="small" onClick={() => acknowledge(r.id)}>
              Xác nhận
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <PageHeader
        title="Cảnh báo"
        subtitle="Theo dõi và xử lý các cảnh báo hệ thống"
        breadcrumbs={[{ title: 'Tổng quan', href: '/' }, { title: 'Cảnh báo' }]}
      />

      <Card style={{ borderRadius: 12 }}>
        <Space style={{ marginBottom: 16 }}>
          <Select
            value={statusFilter}
            onChange={(v) => setStatusFilter(v)}
            options={[
              { value: '', label: 'Tất cả trạng thái' },
              { value: 'OPEN', label: 'Mới' },
              { value: 'IN_PROGRESS', label: 'Đang xử lý' },
              { value: 'RESOLVED', label: 'Đã giải quyết' },
              { value: 'CLOSED', label: 'Đã đóng' },
            ]}
            style={{ width: 160 }}
          />
          <Select
            value={severity}
            onChange={(v) => setSeverity(v)}
            options={[
              { value: '', label: 'Tất cả mức độ' },
              { value: 'LOW', label: 'Thấp' },
              { value: 'MEDIUM', label: 'Trung bình' },
              { value: 'HIGH', label: 'Cao' },
              { value: 'CRITICAL', label: 'Nghiêm trọng' },
            ]}
            style={{ width: 160 }}
          />
        </Space>

        <Table
          columns={columns}
          dataSource={filtered}
          rowKey="id"
          loading={isLoading}
          pagination={{
            pageSize: 20,
            showTotal: (t) => `Tổng ${t} cảnh báo`,
          }}
        />
      </Card>
    </div>
  )
}
