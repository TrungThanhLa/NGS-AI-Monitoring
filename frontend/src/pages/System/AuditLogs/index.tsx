import { Card, DatePicker, Input, Select, Space, Table } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useState } from 'react'
import PageHeader from '@/components/common/PageHeader'
import { auditLogs as mockAuditLogs } from '@/data/mockData'
import dayjs from 'dayjs'

type LogRow = (typeof mockAuditLogs)[number]

// Giá trị action thật xuất hiện trong mockData.ts (auditLogs): LOGIN/CREATE/UPDATE/DELETE/
// VIEW/EXPORT — thêm VIEW so với bản gốc ngs-monitoring-ui (chỉ có LOGIN/LOGOUT/CREATE/
// UPDATE/DELETE/EXPORT) để khớp đủ giá trị thật trong data mẫu (Task 12)
const ACTION_COLORS: Record<string, string> = {
  LOGIN: '#1890FF',
  LOGOUT: '#8C95A0',
  CREATE: '#52C41A',
  UPDATE: '#FAAD14',
  DELETE: '#F5222D',
  VIEW: '#722ED1',
  EXPORT: '#00859A',
}

export default function AuditLogsPage() {
  const [keyword, setKeyword] = useState('')
  const [action, setAction] = useState<string | undefined>()

  const filtered = mockAuditLogs.filter((log) =>
    (!keyword || log.user.username.toLowerCase().includes(keyword.toLowerCase()) || log.user.full_name.toLowerCase().includes(keyword.toLowerCase())) &&
    (!action || log.action === action),
  )

  const columns = [
    { title: 'Người dùng', key: 'user', render: (_: unknown, r: LogRow) => r.user.full_name },
    {
      title: 'Hành động',
      dataIndex: 'action',
      key: 'action',
      render: (v: string) => (
        <span style={{ color: ACTION_COLORS[v] ?? '#1890FF', fontWeight: 500 }}>
          {v}
        </span>
      ),
    },
    { title: 'Đối tượng', dataIndex: 'resource', key: 'resource' },
    { title: 'ID đối tượng', dataIndex: 'resource_id', key: 'resource_id', ellipsis: true },
    { title: 'IP', dataIndex: 'ip_address', key: 'ip_address' },
    {
      title: 'Thời gian', dataIndex: 'created_at', key: 'created_at',
      render: (v: string) => dayjs(v).format('DD/MM/YYYY HH:mm'),
    },
  ]

  return (
    <div>
      <PageHeader
        title="Nhật ký hoạt động"
        breadcrumbs={[{ title: 'Tổng quan', href: '/' }, { title: 'Cấu hình hệ thống' }, { title: 'Nhật ký' }]}
      />

      <Card style={{ borderRadius: 12 }}>
        <Space style={{ marginBottom: 16 }}>
          <Input
            placeholder="Tìm kiếm người dùng..."
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 240 }}
            allowClear
          />
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
              { value: 'DELETE', label: 'Xóa' },
              { value: 'VIEW', label: 'Xem' },
              { value: 'EXPORT', label: 'Xuất file' },
            ]}
          />
          <DatePicker.RangePicker format="DD/MM/YYYY" />
        </Space>

        <Table
          columns={columns}
          dataSource={filtered}
          rowKey="id"
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  )
}
