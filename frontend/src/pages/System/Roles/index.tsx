import { useState, useMemo } from 'react'
import {
  App, Button, Dropdown, Form, Input, Modal, Select, Space,
  Switch, Table, Tag, Tooltip, Typography,
} from 'antd'
import {
  PlusOutlined, EditOutlined,
  DownloadOutlined, UploadOutlined, ReloadOutlined,
  SearchOutlined, MoreOutlined,
} from '@ant-design/icons'
import { roles as mockRoles } from '@/data/mockData'
import dayjs from 'dayjs'

const { Title, Text } = Typography

type RoleRow = (typeof mockRoles)[number]

// ─── Constants ────────────────────────────────────────────────────────────────
// Giá trị thật xuất hiện trong mockData.ts (roles): ACTIVE, SUSPENDED, INACTIVE — không có
// StatusTag type="role" tương ứng (chỉ hỗ trợ campaign/content/alert/case/sentiment/source/user),
// nên giữ local map thay vì mở rộng StatusTag.tsx cho 1 trang mock thuần (Task 10 dùng cùng pattern)
const STATUS_CFG: Record<string, { label: string; color: string }> = {
  ACTIVE:    { label: 'Đang hoạt động', color: 'success' },
  SUSPENDED: { label: 'Tạm ngưng',      color: 'warning' },
  INACTIVE:  { label: 'Không hoạt động',color: 'default' },
}

const CODE_COLOR: Record<string, { bg: string; color: string; border: string }> = {
  ADMIN:    { bg: '#e6f4f7', color: '#006778', border: '#00859A' },
  EDITOR:   { bg: '#e6f0ff', color: '#0040bf', border: '#1677ff' },
  VIEWER:   { bg: '#f6ffed', color: '#389e0d', border: '#52c41a' },
  AUDITOR:  { bg: '#fff7e6', color: '#d46b08', border: '#fa8c16' },
  OPERATOR: { bg: '#f9f0ff', color: '#531dab', border: '#722ed1' },
  GUEST:    { bg: '#fafafa', color: '#595959', border: '#8C95A0' },
}

function RoleCodeTag({ code }: { code: string }) {
  const cfg = CODE_COLOR[code] ?? CODE_COLOR.GUEST
  return (
    <span style={{
      display: 'inline-block',
      padding: '1px 8px', borderRadius: 4,
      background: cfg.bg, color: cfg.color,
      border: `1px solid ${cfg.border}`,
      fontSize: 12, fontWeight: 600, fontFamily: 'monospace',
      letterSpacing: 0.3,
    }}>
      {code}
    </span>
  )
}

// ─── Role Form Modal ───────────────────────────────────────────────────────────
interface RoleModalProps {
  open: boolean
  editRole: RoleRow | null
  onClose: () => void
  onSaved: () => void
}

function RoleFormModal({ open, editRole, onClose, onSaved }: RoleModalProps) {
  const isEdit = !!editRole
  const [form] = Form.useForm()
  const { message } = App.useApp()

  const handleOk = () => {
    form.validateFields().then(() => {
      message.success(isEdit ? 'Cập nhật thành công' : 'Thêm nhóm quyền thành công')
      message.info('Đây là giao diện minh hoạ — chưa lưu được thật')
      onSaved()
      onClose()
    }).catch(() => {})
  }

  return (
    <Modal
      open={open}
      onCancel={onClose}
      onOk={handleOk}
      okText="Lưu"
      cancelText="Huỷ"
      width={560}
      destroyOnClose
      title={
        <Text strong style={{ fontSize: 16, color: '#0A1D55' }}>
          {isEdit ? 'Chỉnh sửa nhóm quyền' : 'Thêm nhóm quyền mới'}
        </Text>
      }
      afterOpenChange={open => {
        if (open && editRole) {
          form.setFieldsValue({
            code:        editRole.code,
            name:        editRole.name,
            description: editRole.description,
            active:      editRole.status === 'ACTIVE',
          })
        } else if (open) {
          form.resetFields()
          form.setFieldsValue({ active: true })
        }
      }}
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item
          name="code"
          label="Mã nhóm quyền"
          rules={[
            { required: true, message: 'Bắt buộc nhập mã' },
            { pattern: /^[A-Z_]+$/, message: 'Chỉ dùng chữ HOA và dấu gạch dưới' },
          ]}
        >
          <Input
            placeholder="VD: CONTENT_REVIEWER"
            disabled={isEdit}
            onChange={e => form.setFieldValue('code', e.target.value.toUpperCase())}
          />
        </Form.Item>

        <Form.Item
          name="name"
          label="Tên nhóm quyền"
          rules={[{ required: true, message: 'Bắt buộc nhập tên' }]}
        >
          <Input placeholder="VD: Người kiểm duyệt nội dung" />
        </Form.Item>

        <Form.Item name="description" label="Mô tả">
          <Input.TextArea rows={3} placeholder="Mô tả nhiệm vụ và phạm vi quyền hạn..." />
        </Form.Item>

        <Form.Item label="Trạng thái">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Form.Item name="active" valuePropName="checked" noStyle>
              <Switch />
            </Form.Item>
            <Text style={{ fontSize: 13 }}>Kích hoạt</Text>
          </div>
        </Form.Item>
      </Form>
    </Modal>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function RolesPage() {
  const { message } = App.useApp()
  const [roles, setRoles] = useState<RoleRow[]>(mockRoles)
  const isLoading = false
  const [keyword, setKeyword]     = useState('')
  const [statusFilter, setStatus] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editRole, setEditRole]   = useState<RoleRow | null>(null)

  const filtered = useMemo(() => {
    return roles.filter((r) =>
      (!keyword ||
        r.name.toLowerCase().includes(keyword.toLowerCase()) ||
        r.description.toLowerCase().includes(keyword.toLowerCase())) &&
      (!statusFilter || r.status === statusFilter),
    )
  }, [roles, keyword, statusFilter])

  // Đổi trạng thái chỉ cập nhật state cục bộ — trang mock thuần, không có backend thật
  const toggleStatus = (id: string, nextStatus: string) => {
    setRoles((prev) => prev.map((r) => (r.id === id ? { ...r, status: nextStatus } : r)))
    message.info('Đây là giao diện minh hoạ — chưa lưu được thật')
  }

  const openCreate = () => { setEditRole(null); setModalOpen(true) }
  const openEdit   = (r: RoleRow) => { setEditRole(r); setModalOpen(true) }

  const columns = [
    {
      title: 'STT', width: 60,
      render: (_: unknown, __: RoleRow, i: number) => (
        <Text type="secondary" style={{ fontSize: 13 }}>{i + 1}</Text>
      ),
    },
    {
      title: 'Tên nhóm quyền', key: 'name',
      render: (_: unknown, r: RoleRow) => (
        <Space size={10} align="center">
          <RoleCodeTag code={r.code} />
          <Text strong style={{ fontSize: 13 }}>{r.name}</Text>
        </Space>
      ),
    },
    {
      title: 'Mô tả', dataIndex: 'description', key: 'description',
      render: (v: string) => <Text style={{ fontSize: 13, color: '#374151' }}>{v}</Text>,
    },
    {
      title: 'Số người dùng', dataIndex: 'user_count', key: 'user_count', width: 130, align: 'center' as const,
      render: (v: number) => (
        <Text style={{ fontSize: 13, fontWeight: 500 }}>{v ?? 0}</Text>
      ),
    },
    {
      title: 'Trạng thái', dataIndex: 'status', key: 'status', width: 160,
      render: (v: string, r: RoleRow) => {
        const cfg = STATUS_CFG[v] ?? STATUS_CFG.INACTIVE
        const isActive = v === 'ACTIVE'
        return (
          <Tooltip title={isActive ? 'Nhấn để tạm ngưng' : 'Nhấn để kích hoạt'}>
            <Tag
              color={cfg.color}
              style={{ borderRadius: 4, fontSize: 12, cursor: 'pointer' }}
              onClick={() => toggleStatus(r.id, isActive ? 'SUSPENDED' : 'ACTIVE')}
            >
              {cfg.label}
            </Tag>
          </Tooltip>
        )
      },
    },
    {
      title: 'Ngày tạo', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (v: string) => (
        <Text style={{ fontSize: 13 }}>{dayjs(v).format('DD/MM/YYYY HH:mm')}</Text>
      ),
    },
    {
      title: 'Thao tác', key: 'actions', width: 90,
      render: (_: unknown, r: RoleRow) => (
        <Space size={4}>
          <Tooltip title="Chỉnh sửa">
            <Button
              type="text" size="small"
              icon={<EditOutlined style={{ color: '#1677ff' }} />}
              onClick={() => openEdit(r)}
            />
          </Tooltip>
          <Dropdown
            menu={{
              items: [
                {
                  key: 'toggle',
                  label: r.status === 'ACTIVE' ? 'Tạm ngưng' : 'Kích hoạt',
                  onClick: () => toggleStatus(r.id, r.status === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE'),
                },
              ],
            }}
            placement="bottomRight"
          >
            <Button type="text" size="small" icon={<MoreOutlined />} />
          </Dropdown>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 112px)' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <Title level={3} style={{ margin: '0 0 4px', color: '#0A1D55' }}>Quản lý nhóm quyền</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>Quản lý các nhóm quyền và phân quyền truy cập hệ thống.</Text>
        </div>
        <Space>
          <Button icon={<DownloadOutlined />}>Xuất Excel</Button>
          <Button icon={<UploadOutlined />}>Nhập Excel</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            Thêm mới
          </Button>
        </Space>
      </div>

      {/* Card */}
      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #f0f0f0', flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Filter bar */}
        <div style={{ padding: '16px 20px 12px', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Input
            prefix={<SearchOutlined style={{ color: '#8c8c8c' }} />}
            placeholder="Tìm kiếm theo tên nhóm quyền, mô tả..."
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            allowClear
            style={{ width: 340 }}
          />
          <Select
            value={statusFilter}
            onChange={v => setStatus(v)}
            style={{ width: 200 }}
            options={[
              { value: '',          label: 'Trạng thái: Tất cả' },
              { value: 'ACTIVE',    label: 'Đang hoạt động' },
              { value: 'SUSPENDED', label: 'Tạm ngưng' },
              { value: 'INACTIVE',  label: 'Không hoạt động' },
            ]}
          />
          <div style={{ flex: 1 }} />
          <Tooltip title="Làm mới">
            <Button icon={<ReloadOutlined />} onClick={() => { setKeyword(''); setStatus('') }}>
              Làm mới
            </Button>
          </Tooltip>
        </div>

        {/* Table */}
        <div style={{ flex: 1, overflow: 'auto', padding: '0 20px' }}>
          <Table
            columns={columns}
            dataSource={filtered}
            rowKey="id"
            loading={isLoading}
            size="middle"
            pagination={{ pageSize: 20, showTotal: (t) => `Tổng ${t} nhóm quyền` }}
          />
        </div>
      </div>

      <RoleFormModal
        open={modalOpen}
        editRole={editRole}
        onClose={() => { setModalOpen(false); setEditRole(null) }}
        onSaved={() => {}}
      />
    </div>
  )
}
