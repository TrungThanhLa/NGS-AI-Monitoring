import { useState, useMemo } from 'react'
import {
  App, Avatar, Button, Input, Select, Space, Table, Tag, Tooltip,
  Typography, Badge,
} from 'antd'
import {
  PlusOutlined, SearchOutlined, EditOutlined,
  LockOutlined, UnlockOutlined,
  DownloadOutlined, UploadOutlined, ReloadOutlined,
} from '@ant-design/icons'
import { users as mockUsers } from '@/data/mockData'
import UserModal from './UserModal'
import dayjs from 'dayjs'

const { Title, Text } = Typography

type UserRow = (typeof mockUsers)[number]

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  ACTIVE:   { color: 'success', label: 'Đang hoạt động' },
  INACTIVE: { color: 'default', label: 'Không hoạt động' },
  LOCKED:   { color: 'warning', label: 'Tạm khóa' },
}

const ROLE_COLOR: Record<string, string> = {
  ADMIN:   '#00859A',
  EDITOR:  '#1677ff',
  MONITOR: '#fa8c16',
  STAFF:   '#722ed1',
}

function UserAvatar({ user }: { user: UserRow }) {
  return (
    <Avatar
      size={32}
      style={{ background: user.avatar_color ?? '#00859A', flexShrink: 0, fontSize: 13, fontWeight: 600 }}
    >
      {user.initials ?? user.full_name?.slice(0, 2).toUpperCase()}
    </Avatar>
  )
}

export default function UsersPage() {
  const { message } = App.useApp()

  const [data, setData] = useState<UserRow[]>(mockUsers)
  const isLoading = false

  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)

  const filtered = useMemo(() => {
    return data.filter((u) =>
      (!keyword ||
        u.full_name.toLowerCase().includes(keyword.toLowerCase()) ||
        u.email.toLowerCase().includes(keyword.toLowerCase()) ||
        u.username.toLowerCase().includes(keyword.toLowerCase())) &&
      (!statusFilter || u.status === statusFilter) &&
      (!roleFilter || u.roles?.some((r) => r.code === roleFilter)),
    )
  }, [data, keyword, statusFilter, roleFilter])

  // Khóa/mở khóa chỉ đổi state cục bộ — không có backend thật đứng sau (trang mock thuần)
  const toggleLock = (id: string) => {
    setData((prev) =>
      prev.map((u) => (u.id === id ? { ...u, status: u.status === 'LOCKED' ? 'ACTIVE' : 'LOCKED' } : u)),
    )
    message.info('Đây là giao diện minh hoạ — chưa lưu được thật')
  }

  const columns = [
    {
      title: 'STT', width: 56,
      render: (_: unknown, __: UserRow, i: number) => (
        <Text type="secondary" style={{ fontSize: 13 }}>{(page - 1) * pageSize + i + 1}</Text>
      ),
    },
    {
      title: 'Họ và tên', key: 'full_name',
      render: (_: unknown, r: UserRow) => (
        <Space size={10}>
          <UserAvatar user={r} />
          <div>
            <Space size={6} align="center">
              <Text strong style={{ fontSize: 13 }}>{r.full_name}</Text>
              {r.is_me && <Tag color="processing" style={{ fontSize: 11, padding: '0 5px', lineHeight: '18px' }}>Bạn</Tag>}
            </Space>
          </div>
        </Space>
      ),
    },
    {
      title: 'Tên đăng nhập', dataIndex: 'username', key: 'username',
      render: (v: string) => <Text style={{ fontSize: 13 }}>{v}</Text>,
    },
    {
      title: 'Email', dataIndex: 'email', key: 'email',
      render: (v: string) => <Text style={{ fontSize: 13, color: '#374151' }}>{v}</Text>,
    },
    {
      title: 'Nhóm quyền', key: 'roles',
      render: (_: unknown, r: UserRow) => (
        r.roles?.length
          ? r.roles.map((role) => (
              <Tag
                key={role.id}
                style={{
                  background: `${ROLE_COLOR[role.code] ?? '#8C95A0'}18`,
                  color: ROLE_COLOR[role.code] ?? '#8C95A0',
                  border: `1px solid ${ROLE_COLOR[role.code] ?? '#8C95A0'}40`,
                  borderRadius: 4, fontSize: 12,
                }}
              >
                {role.name}
              </Tag>
            ))
          : <Text type="secondary">—</Text>
      ),
    },
    {
      title: 'Trạng thái', dataIndex: 'status', key: 'status', width: 140,
      render: (v: string, r: UserRow) => {
        const cfg = STATUS_CONFIG[v] ?? STATUS_CONFIG.INACTIVE
        return (
          <Tooltip title={v === 'LOCKED' && r.failed_login_count > 0 ? `Đăng nhập sai ${r.failed_login_count} lần` : ''}>
            <Badge count={v === 'LOCKED' ? r.failed_login_count : 0} size="small" offset={[4, 0]}>
              <Tag color={cfg.color} style={{ borderRadius: 4, fontSize: 12 }}>{cfg.label}</Tag>
            </Badge>
          </Tooltip>
        )
      },
    },
    {
      title: 'Lần đăng nhập cuối', dataIndex: 'last_login_at', key: 'last_login_at', width: 155,
      render: (v: string) => v
        ? <Text style={{ fontSize: 13 }}>{dayjs(v).format('DD/MM/YYYY HH:mm')}</Text>
        : <Text type="secondary" style={{ fontSize: 12 }}>Chưa đăng nhập</Text>,
    },
    {
      title: 'Thao tác', key: 'actions', width: 80,
      render: (_: unknown, r: UserRow) => (
        <Space size={2}>
          <Tooltip title="Chỉnh sửa">
            <Button type="text" size="small" icon={<EditOutlined style={{ color: '#1677ff' }} />}
              onClick={() => { setEditId(r.id); setModalOpen(true) }} />
          </Tooltip>
          <Tooltip title={r.status === 'LOCKED' ? 'Mở khóa' : 'Khóa tài khoản'}>
            {r.status === 'LOCKED'
              ? <Button type="text" size="small" icon={<UnlockOutlined style={{ color: '#52c41a' }} />} onClick={() => toggleLock(r.id)} />
              : <Button type="text" size="small" icon={<LockOutlined style={{ color: '#8C95A0' }} />} onClick={() => toggleLock(r.id)} />
            }
          </Tooltip>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 112px)' }}>
      {/* Page header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <Title level={3} style={{ margin: '0 0 4px', color: '#0A1D55' }}>Quản lý người dùng</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>Quản lý tài khoản người dùng và phân quyền truy cập hệ thống.</Text>
        </div>
        <Space>
          <Button icon={<DownloadOutlined />}>Xuất Excel</Button>
          <Button icon={<UploadOutlined />}>Nhập Excel</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditId(null); setModalOpen(true) }}>
            Thêm mới
          </Button>
        </Space>
      </div>

      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #f0f0f0', flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Filter bar */}
        <div style={{ padding: '16px 20px 0', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Input
            prefix={<SearchOutlined style={{ color: '#8c8c8c' }} />}
            placeholder="Tìm kiếm theo tên, email, tên đăng nhập..."
            value={keyword}
            onChange={e => { setKeyword(e.target.value); setPage(1) }}
            allowClear
            style={{ width: 320 }}
          />
          <Select
            value={statusFilter}
            onChange={v => { setStatusFilter(v); setPage(1) }}
            style={{ width: 180 }}
            options={[
              { value: '',         label: 'Trạng thái: Tất cả' },
              { value: 'ACTIVE',   label: 'Đang hoạt động' },
              { value: 'LOCKED',   label: 'Tạm khóa' },
              { value: 'INACTIVE', label: 'Không hoạt động' },
            ]}
          />
          <Select
            value={roleFilter}
            onChange={v => { setRoleFilter(v); setPage(1) }}
            style={{ width: 200 }}
            options={[
              { value: '',        label: 'Nhóm quyền: Tất cả' },
              { value: 'ADMIN',   label: 'Quản trị hệ thống' },
              { value: 'EDITOR',  label: 'Biên tập viên' },
              { value: 'MONITOR', label: 'Giám sát viên' },
              { value: 'STAFF',   label: 'Nhân viên' },
            ]}
          />
          <Tooltip title="Làm mới">
            <Button icon={<ReloadOutlined />} onClick={() => { setKeyword(''); setStatusFilter(''); setRoleFilter('') }}>
              Làm mới
            </Button>
          </Tooltip>
        </div>

        {/* Table */}
        <div style={{ flex: 1, overflow: 'auto', padding: '12px 20px 0' }}>
          <Table
            columns={columns}
            dataSource={filtered}
            rowKey="id"
            loading={isLoading}
            size="middle"
            scroll={{ x: 1000 }}
            pagination={{
              current: page,
              pageSize,
              total: filtered.length,
              onChange: (p, ps) => { setPage(p); setPageSize(ps) },
              showTotal: (total, [s, e]) => `Hiển thị ${s} - ${e} của ${total} bản ghi`,
              showSizeChanger: true,
              pageSizeOptions: ['10', '20', '50'],
            }}
          />
        </div>
      </div>

      <UserModal
        open={modalOpen}
        editId={editId}
        onClose={() => { setModalOpen(false); setEditId(null) }}
        onSavedAndNew={() => { /* modal resets itself */ }}
      />
    </div>
  )
}
