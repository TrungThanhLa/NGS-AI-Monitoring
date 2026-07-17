// frontend/src/pages/System/Roles/index.tsx
import { useEffect, useState } from 'react'
import { Button, Checkbox, Form, Input, Modal, Space, Table, Tag, Tooltip, Typography } from 'antd'
import { PlusOutlined, LockOutlined } from '@ant-design/icons'
import { authFetch } from '@/lib/api'

const { Title, Text } = Typography

type RoleRow = {
  role_id: string
  code: string
  name: string
  is_system: boolean
  permissions: string[]
  user_count: number
}

// Màu cố định cho đúng 5 role hệ thống (rule 15) — không có role nào khác
const ROLE_COLOR: Record<string, string> = {
  ADMIN: 'geekblue',
  MANAGER: 'purple',
  ANALYST: 'blue',
  OPERATOR: 'orange',
  VIEWER: 'default',
}

// Ép tiêu đề cột không xuống dòng — AntD Table wrap tiêu đề khi width cột hẹp hơn
// text dù bảng còn dư khoảng trống ở cột khác
function nowrap(title: string) {
  return <span style={{ whiteSpace: 'nowrap' }}>{title}</span>
}

// 25 permission thật (migration 0011/0013) — dùng cho checkbox tĩnh minh họa ở modal
// "Đang phát triển", KHÔNG phải nguồn dữ liệu để tạo role thật
const ALL_PERMISSIONS = [
  'dashboard.view',
  'campaign.view', 'campaign.create', 'campaign.update', 'campaign.archive',
  'source.view', 'source.create', 'source.update', 'source.delete',
  'content.view', 'content.review',
  'alert.view', 'alert.acknowledge', 'alert.update', 'alert.close',
  'case.view', 'case.create', 'case.update', 'case.close',
  'report.view', 'report.create',
  'user.manage', 'role.manage', 'audit_log.view', 'system.configure',
]

// ─── Modal tạo role — GIAO DIỆN TĨNH, phủ overlay "Đang phát triển" (xem
// docs/superpowers/specs/2026-07-17-phase1-auth-rbac-completion-design.md
// mục "Ghi chú roadmap — Custom Role" + ROADMAP_CONTINUOUS_MONITORING.md Phase 10).
// Không gọi API thật — POST /api/roles chưa tồn tại.
function StaticRoleFormModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [form] = Form.useForm()
  return (
    <Modal open={open} onCancel={onClose} footer={null} width={640} destroyOnClose title="Thêm nhóm quyền mới">
      <div style={{ position: 'relative' }}>
        <div
          style={{
            position: 'absolute', inset: 0, zIndex: 10,
            background: 'rgba(255,255,255,0.75)',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8,
            borderRadius: 8,
          }}
        >
          <LockOutlined style={{ fontSize: 28, color: '#8C95A0' }} />
          <Text strong style={{ fontSize: 16, color: '#374151' }}>Đang phát triển</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>Tính năng tạo nhóm quyền tùy chỉnh sẽ mở ở giai đoạn sau</Text>
        </div>

        <Form form={form} layout="vertical" disabled>
          <Form.Item name="code" label="Mã nhóm quyền">
            <Input placeholder="VD: CONTENT_REVIEWER" />
          </Form.Item>
          <Form.Item name="name" label="Tên nhóm quyền">
            <Input placeholder="VD: Người kiểm duyệt nội dung" />
          </Form.Item>
          <Form.Item label="Chọn quyền">
            <Checkbox.Group options={ALL_PERMISSIONS} style={{ display: 'flex', flexDirection: 'column', gap: 4 }} />
          </Form.Item>
        </Form>
      </div>
    </Modal>
  )
}

export default function RolesPage() {
  const [roles, setRoles] = useState<RoleRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)

  useEffect(() => {
    authFetch('/api/roles')
      .then((res) => (res.ok ? res.json() : { roles: [] }))
      .then((body) => {
        setRoles(body.roles ?? [])
        setError(null)
      })
      .catch(() => setError('Không tải được danh sách vai trò'))
      .finally(() => setLoading(false))
  }, [])

  const columns = [
    { title: nowrap('Mã'), dataIndex: 'code', key: 'code', render: (v: string) => <Tag color={ROLE_COLOR[v] ?? 'default'}>{v}</Tag> },
    { title: nowrap('Tên nhóm quyền'), dataIndex: 'name', key: 'name' },
    { title: nowrap('Số người dùng'), dataIndex: 'user_count', key: 'user_count', width: 150, align: 'center' as const },
    {
      title: nowrap('Quyền'), key: 'permissions',
      render: (_: unknown, r: RoleRow) => (
        <Space size={[4, 4]} wrap>
          {r.permissions.map((p) => <Tag key={p} style={{ fontSize: 11 }}>{p}</Tag>)}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <Title level={3} style={{ margin: '0 0 4px', color: '#0A1D55' }}>Quản lý nhóm quyền</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>5 vai trò hệ thống cố định — không tạo/sửa/xóa được qua giao diện.</Text>
        </div>
        <Tooltip title="Tính năng tạo nhóm quyền tùy chỉnh đang phát triển">
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>Thêm mới</Button>
        </Tooltip>
      </div>

      {error && (
        <Typography.Text type="danger" style={{ display: 'block', marginBottom: 16 }}>
          {error}
        </Typography.Text>
      )}

      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #f0f0f0', padding: 16 }}>
        <Table columns={columns} dataSource={roles} rowKey="role_id" loading={loading} pagination={false} />
      </div>

      <StaticRoleFormModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  )
}
