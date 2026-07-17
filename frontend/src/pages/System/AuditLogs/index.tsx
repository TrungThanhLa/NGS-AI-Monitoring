import { Card, DatePicker, Select, Space, Table, Typography } from 'antd'
import { useEffect, useState } from 'react'
import PageHeader from '@/components/common/PageHeader'
import { authFetch } from '@/lib/api'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

type LogRow = {
  audit_id: string
  action: string
  entity_type: string | null
  entity_id: string | null
  username: string | null
  full_name: string | null
  ip_address: string | null
  created_at: string | null
}

const ACTION_COLORS: Record<string, string> = {
  LOGIN: '#1890FF',
  CREATE: '#52C41A',
  UPDATE: '#FAAD14',
}

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<LogRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [action, setAction] = useState<string | undefined>()
  const [dateRange, setDateRange] = useState<[string, string] | null>(null)

  useEffect(() => {
    const params = new URLSearchParams()
    if (action) params.set('action', action)
    if (dateRange) {
      params.set('date_from', dateRange[0])
      params.set('date_to', dateRange[1])
    }
    setLoading(true)
    authFetch(`/api/audit-logs?${params.toString()}`)
      .then((res) => (res.ok ? res.json() : { audit_logs: [] }))
      .then((body) => {
        setLogs(body.audit_logs ?? [])
        setError(null)
      })
      .catch(() => setError('Không tải được nhật ký hoạt động'))
      .finally(() => setLoading(false))
  }, [action, dateRange])

  const columns = [
    { title: 'Người dùng', key: 'user', render: (_: unknown, r: LogRow) => r.full_name ?? r.username ?? '—' },
    {
      title: 'Hành động', dataIndex: 'action', key: 'action',
      render: (v: string) => <span style={{ color: ACTION_COLORS[v] ?? '#1890FF', fontWeight: 500 }}>{v}</span>,
    },
    { title: 'Đối tượng', dataIndex: 'entity_type', key: 'entity_type', render: (v: string | null) => v ?? '—' },
    { title: 'IP', dataIndex: 'ip_address', key: 'ip_address', render: (v: string | null) => v ?? '—' },
    {
      title: 'Thời gian', dataIndex: 'created_at', key: 'created_at',
      render: (v: string | null) => (v ? dayjs(v).format('DD/MM/YYYY HH:mm') : '—'),
    },
  ]

  return (
    <div>
      <PageHeader
        title="Nhật ký hoạt động"
        breadcrumbs={[{ title: 'Tổng quan', href: '/' }, { title: 'Cấu hình hệ thống' }, { title: 'Nhật ký' }]}
      />

      {error && (
        <Typography.Text type="danger" style={{ display: 'block', marginBottom: 16 }}>
          {error}
        </Typography.Text>
      )}

      <Card style={{ borderRadius: 12 }}>
        <Space style={{ marginBottom: 16 }}>
          <Select
            placeholder="Loại hành động"
            allowClear
            value={action}
            onChange={setAction}
            style={{ width: 160 }}
            options={[
              { value: 'LOGIN', label: 'Đăng nhập' },
              { value: 'CREATE', label: 'Tạo mới' },
              { value: 'UPDATE', label: 'Cập nhật' },
            ]}
          />
          <RangePicker
            format="DD/MM/YYYY"
            onChange={(_, dateStrings) => {
              if (!dateStrings[0] || !dateStrings[1]) { setDateRange(null); return }
              setDateRange([dayjs(dateStrings[0], 'DD/MM/YYYY').format('YYYY-MM-DD'), dayjs(dateStrings[1], 'DD/MM/YYYY').format('YYYY-MM-DD')])
            }}
          />
        </Space>

        <Table columns={columns} dataSource={logs} rowKey="audit_id" loading={loading} pagination={{ pageSize: 20 }} />
      </Card>
    </div>
  )
}
