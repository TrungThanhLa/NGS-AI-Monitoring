import { useEffect, useState, useCallback } from 'react'
import { App, Avatar, Button, Input, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import { PlusOutlined, SearchOutlined, EditOutlined, LockOutlined, UnlockOutlined, ReloadOutlined } from '@ant-design/icons'
import { authFetch } from '@/lib/api'
import UserModal from './UserModal'
import dayjs from 'dayjs'

const { Title, Text } = Typography

type UserRow = {
  user_id: string
  username: string
  full_name: string | null
  email: string | null
  status: string
  roles: string[]
  last_login_at: string | null
}

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  ACTIVE: { color: 'success', label: 'Đang hoạt động' },
  INACTIVE: { color: 'default', label: 'Không hoạt động' },
  LOCKED: { color: 'warning', label: 'Tạm khóa' },
}

export default function UsersPage() {
  const { message } = App.useApp()
  const [data, setData] = useState<UserRow[]>([])
  const [loading, setLoading] = useState(true)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)

  const loadUsers = useCallback(() => {
    setLoading(true)
    authFetch('/api/users')
      .then((res) => (res.ok ? res.json() : { users: [] }))
      .then((body) => setData(body.users ?? []))
      .catch(() => message.error('Không tải được danh sách người dùng'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadUsers() }, [loadUsers])

  const filtered = data.filter((u) =>
    (!keyword ||
      (u.full_name ?? '').toLowerCase().includes(keyword.toLowerCase()) ||
      (u.email ?? '').toLowerCase().includes(keyword.toLowerCase()) ||
      u.username.toLowerCase().includes(keyword.toLowerCase())) &&
    (!statusFilter || u.status === statusFilter),
  )

  const toggleLock = async (row: UserRow) => {
    const nextStatus = row.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'
    const res = await authFetch(`/api/users/${row.user_id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: nextStatus }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: 'Không thể cập nhật trạng thái' }))
      message.error(body.detail ?? 'Không thể cập nhật trạng thái')
      return
    }
    message.success('Cập nhật trạng thái thành công')
    loadUsers()
  }

  const columns = [
    {
      title: 'Họ và tên', key: 'full_name',
      render: (_: unknown, r: UserRow) => (
        <Space size={10}>
          <Avatar size={32} style={{ background: '#00859A', fontSize: 13, fontWeight: 600 }}>
            {(r.full_name ?? r.username).slice(0, 2).toUpperCase()}
          </Avatar>
          <Text strong style={{ fontSize: 13 }}>{r.full_name ?? '—'}</Text>
        </Space>
      ),
    },
    { title: 'Tên đăng nhập', dataIndex: 'username', key: 'username' },
    { title: 'Email', dataIndex: 'email', key: 'email', render: (v: string | null) => v ?? '—' },
    {
      title: 'Vai trò', key: 'roles',
      render: (_: unknown, r: UserRow) => r.roles.map((code) => <Tag key={code}>{code}</Tag>),
    },
    {
      title: 'Trạng thái', dataIndex: 'status', key: 'status', width: 140,
      render: (v: string) => {
        const cfg = STATUS_CONFIG[v] ?? STATUS_CONFIG.INACTIVE
        return <Tag color={cfg.color}>{cfg.label}</Tag>
      },
    },
    {
      title: 'Lần đăng nhập cuối', dataIndex: 'last_login_at', key: 'last_login_at', width: 155,
      render: (v: string | null) => (v ? dayjs(v).format('DD/MM/YYYY HH:mm') : <Text type="secondary">Chưa đăng nhập</Text>),
    },
    {
      title: 'Thao tác', key: 'actions', width: 80,
      render: (_: unknown, r: UserRow) => (
        <Space size={2}>
          <Tooltip title="Chỉnh sửa">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => { setEditId(r.user_id); setModalOpen(true) }} />
          </Tooltip>
          <Tooltip title={r.status === 'ACTIVE' ? 'Vô hiệu hóa' : 'Kích hoạt lại'}>
            <Button
              type="text" size="small"
              icon={r.status === 'ACTIVE' ? <LockOutlined /> : <UnlockOutlined />}
              onClick={() => toggleLock(r)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <Title level={3} style={{ margin: '0 0 4px', color: '#0A1D55' }}>Quản lý người dùng</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>Quản lý tài khoản người dùng và phân quyền truy cập hệ thống.</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditId(null); setModalOpen(true) }}>
          Thêm mới
        </Button>
      </div>

      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #f0f0f0', padding: 16 }}>
        <Space style={{ marginBottom: 16 }}>
          <Input
            prefix={<SearchOutlined />}
            placeholder="Tìm kiếm theo tên, email, tên đăng nhập..."
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            allowClear
            style={{ width: 320 }}
          />
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            style={{ width: 180 }}
            options={[
              { value: '', label: 'Trạng thái: Tất cả' },
              { value: 'ACTIVE', label: 'Đang hoạt động' },
              { value: 'INACTIVE', label: 'Không hoạt động' },
            ]}
          />
          <Tooltip title="Làm mới">
            <Button icon={<ReloadOutlined />} onClick={loadUsers} />
          </Tooltip>
        </Space>

        <Table columns={columns} dataSource={filtered} rowKey="user_id" loading={loading} pagination={{ pageSize: 20 }} />
      </div>

      <UserModal
        open={modalOpen}
        editId={editId}
        onClose={() => { setModalOpen(false); setEditId(null) }}
        onSaved={loadUsers}
      />
    </div>
  )
}
