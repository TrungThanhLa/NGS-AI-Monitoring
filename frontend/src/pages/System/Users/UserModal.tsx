import { useEffect, useRef, useState } from 'react'
import {
  App, Modal, Form, Input, Select, Switch, Tabs, Row, Col,
  Checkbox, Typography, Space, Button, DatePicker,
  Divider, Avatar,
} from 'antd'
import {
  UserOutlined, UploadOutlined, DownOutlined, RightOutlined,
  HomeOutlined, GlobalOutlined, FileTextOutlined,
  BellOutlined, BarChartOutlined, SettingOutlined,
  TeamOutlined, AuditOutlined, TagsOutlined, KeyOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import { users as mockUsers, roles as mockRoles } from '@/data/mockData'

const { Text } = Typography

// ─── Password rules ────────────────────────────────────────────────────────────
const PASSWORD_RULES = [
  { required: true, message: 'Vui lòng nhập mật khẩu' },
  { min: 8, message: 'Tối thiểu 8 ký tự' },
  {
    validator: (_: unknown, value: string) => {
      if (!value) return Promise.resolve()
      if (!/[A-Z]/.test(value)) return Promise.reject('Cần ít nhất 1 chữ hoa (A-Z)')
      if (!/[a-z]/.test(value)) return Promise.reject('Cần ít nhất 1 chữ thường (a-z)')
      if (!/\d/.test(value)) return Promise.reject('Cần ít nhất 1 chữ số (0-9)')
      return Promise.resolve()
    },
  },
]

// ─── Permission tree ───────────────────────────────────────────────────────────
type PermNode = {
  key: string
  label: string
  icon?: React.ReactNode
  children?: PermNode[]
}

const PERM_TREE: PermNode[] = [
  { key: 'dashboard',  label: 'Tổng quan',               icon: <HomeOutlined /> },
  { key: 'source',     label: 'Nguồn dữ liệu',           icon: <GlobalOutlined /> },
  { key: 'content',    label: 'Nội dung',                 icon: <FileTextOutlined /> },
  { key: 'alert',      label: 'Cảnh báo',                 icon: <BellOutlined /> },
  { key: 'report',     label: 'Báo cáo',                  icon: <BarChartOutlined /> },
  {
    key: 'system',
    label: 'Cấu hình hệ thống',
    icon: <SettingOutlined />,
    children: [
      { key: 'system.masterdata',    label: 'Dữ liệu dùng chung',         icon: <TagsOutlined /> },
      {
        key: 'system.users',
        label: 'Người dùng & phân quyền',
        icon: <TeamOutlined />,
        children: [
          { key: 'system.users.roles', label: 'Nhóm quyền',        icon: <KeyOutlined /> },
          { key: 'system.users.audit', label: 'Nhật ký hệ thống',  icon: <AuditOutlined /> },
        ],
      },
      { key: 'system.alert_config', label: 'Cấu hình cảnh báo',   icon: <BellOutlined /> },
      { key: 'system.crawler',      label: 'Cấu hình crawler',     icon: <SettingOutlined /> },
      { key: 'system.connector',    label: 'Cấu hình connector',   icon: <SettingOutlined /> },
      { key: 'system.report',       label: 'Cấu hình báo cáo',    icon: <BarChartOutlined /> },
      { key: 'system.settings',     label: 'Tham số hệ thống',    icon: <SettingOutlined /> },
    ],
  },
]

const ROLE_PERMS: Record<string, string[]> = {
  ADMIN:   ['dashboard','source','content','alert','report','system','system.masterdata','system.users','system.users.roles','system.users.audit','system.alert_config','system.crawler','system.connector','system.report','system.settings'],
  EDITOR:  ['dashboard','source','content','report'],
  VIEWER:  ['dashboard','source','content','alert','report'],
  AUDITOR: ['dashboard','content'],
}

const DEPT_OPTIONS = [
  { value: 'TECH',    label: 'Phòng Kỹ thuật' },
  { value: 'CONTENT', label: 'Phòng Nội dung' },
  { value: 'MONITOR', label: 'Phòng Giám sát' },
  { value: 'ADMIN',   label: 'Phòng Hành chính' },
  { value: 'MANAGE',  label: 'Ban Quản lý' },
]

// ─── File validation ───────────────────────────────────────────────────────────
function validateImageFile(file: File): string | null {
  const ALLOWED = ['image/jpeg', 'image/png', 'image/webp']
  if (!ALLOWED.includes(file.type)) return 'Chỉ chấp nhận định dạng JPG, PNG hoặc WEBP'
  if (file.size > 2 * 1024 * 1024) return 'Ảnh không được vượt quá 2MB'
  return null
}

// ─── Permission tree component ─────────────────────────────────────────────────
function PermTree({
  nodes, checked, onChange,
}: { nodes: PermNode[]; checked: string[]; onChange: (keys: string[]) => void }) {
  const [expanded, setExpanded] = useState<string[]>(['system'])

  const toggleExpand = (key: string) => {
    setExpanded(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key])
  }

  const getAllKeys = (node: PermNode): string[] => [
    node.key, ...(node.children?.flatMap(getAllKeys) ?? []),
  ]

  const isChecked  = (node: PermNode) => getAllKeys(node).every(k => checked.includes(k))
  const isIndet    = (node: PermNode) => {
    const all = getAllKeys(node)
    return all.some(k => checked.includes(k)) && !all.every(k => checked.includes(k))
  }

  const toggle = (node: PermNode, add: boolean) => {
    const all = getAllKeys(node)
    onChange(add ? [...new Set([...checked, ...all])] : checked.filter(k => !all.includes(k)))
  }

  const renderNode = (node: PermNode, depth = 0) => {
    const hasChildren = (node.children?.length ?? 0) > 0
    const isOpen = expanded.includes(node.key)

    return (
      <div key={node.key}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: `6px ${depth * 20 + 8}px`,
          borderRadius: 6,
          background: isChecked(node) ? '#f0f7ff' : 'transparent',
        }}>
          <Checkbox
            checked={isChecked(node)}
            indeterminate={isIndet(node)}
            onChange={e => toggle(node, e.target.checked)}
          />
          {hasChildren && (
            <span
              style={{ fontSize: 11, color: '#8c8c8c', cursor: 'pointer', width: 14 }}
              onClick={() => toggleExpand(node.key)}
            >
              {isOpen ? <DownOutlined /> : <RightOutlined />}
            </span>
          )}
          <span style={{ color: '#6b7280', fontSize: 14 }}>{node.icon}</span>
          <Text style={{ fontSize: 13 }}>{node.label}</Text>
        </div>
        {hasChildren && isOpen && node.children?.map(c => renderNode(c, depth + 1))}
      </div>
    )
  }

  const allKeys    = PERM_TREE.flatMap(getAllKeys)
  const allChecked = allKeys.every(k => checked.includes(k))
  const anyChecked = allKeys.some(k => checked.includes(k))

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px', borderBottom: '1px solid #f0f0f0', marginBottom: 4 }}>
        <Checkbox
          checked={allChecked}
          indeterminate={anyChecked && !allChecked}
          onChange={e => onChange(e.target.checked ? allKeys : [])}
        />
        <Text style={{ fontSize: 13, color: '#374151' }}>Chọn tất cả quyền</Text>
      </div>
      {nodes.map(n => renderNode(n, 0))}
    </div>
  )
}

// ─── Avatar upload zone (mock — chỉ preview cục bộ, không tải lên thật) ────────
interface AvatarUploadProps {
  initials: string
  avatarColor: string
  existingUrl?: string
  onUploaded: (url: string) => void
}

function AvatarUpload({ initials, avatarColor, existingUrl, onUploaded }: AvatarUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(existingUrl ?? null)
  const { message } = App.useApp()

  // Reset khi modal đóng/mở lại
  useEffect(() => { setPreviewUrl(existingUrl ?? null) }, [existingUrl])

  const handleFile = (file: File) => {
    const err = validateImageFile(file)
    if (err) { message.error(err); return }

    // Giao diện minh hoạ — chỉ hiện preview cục bộ, không tải lên server thật
    const localUrl = URL.createObjectURL(file)
    setPreviewUrl(localUrl)
    onUploaded(localUrl)
    message.info('Đây là giao diện minh hoạ — ảnh chưa được tải lên thật')
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''   // reset để có thể chọn lại cùng file
  }

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation()
    setPreviewUrl(null)
    onUploaded('')
  }

  return (
    <div
      onDragOver={e => e.preventDefault()}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      style={{
        border: '1px dashed #d0d5dd',
        borderRadius: 8,
        background: '#fafafa',
        cursor: 'pointer',
        padding: '10px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        transition: 'border-color .2s',
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = '#00859A')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = '#d0d5dd')}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".jpg,.jpeg,.png,.webp"
        style={{ display: 'none' }}
        onChange={handleInputChange}
      />

      {/* Preview / placeholder */}
      <div style={{ position: 'relative', flexShrink: 0 }}>
        {previewUrl ? (
          <img
            src={previewUrl}
            alt="avatar"
            style={{ width: 56, height: 56, borderRadius: 8, objectFit: 'cover', display: 'block' }}
          />
        ) : (
          <Avatar
            size={56}
            style={{ background: avatarColor, borderRadius: 8, fontSize: 20, fontWeight: 700 }}
          >
            {initials || <UserOutlined />}
          </Avatar>
        )}
        {previewUrl && (
          <Button
            type="text"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={handleRemove}
            style={{
              position: 'absolute', top: -8, right: -8,
              background: '#fff', border: '1px solid #ffa39e',
              borderRadius: '50%', width: 22, height: 22,
              padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11,
            }}
          />
        )}
      </div>

      {/* Text + button */}
      <div style={{ flex: 1 }}>
        <Text style={{ fontSize: 13, color: '#374151', display: 'block' }}>
          {previewUrl ? 'Ảnh đã tải lên — nhấn để thay đổi' : 'Kéo thả ảnh vào đây hoặc nhấn chọn'}
        </Text>
        <Text type="secondary" style={{ fontSize: 12 }}>JPG, PNG, WEBP — tối đa 2MB</Text>
      </div>

      <Button
        size="small"
        icon={<UploadOutlined />}
        onClick={e => { e.stopPropagation(); inputRef.current?.click() }}
      >
        {previewUrl ? 'Thay ảnh' : 'Chọn ảnh'}
      </Button>
    </div>
  )
}

// ─── Main modal ────────────────────────────────────────────────────────────────
interface Props {
  open: boolean
  editId?: string | null
  onClose: () => void
  onSavedAndNew?: () => void
}

export default function UserModal({ open, editId, onClose, onSavedAndNew }: Props) {
  const isEdit = !!editId
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [checkedPerms, setCheckedPerms] = useState<string[]>([])
  const [avatarUrl, setAvatarUrl] = useState<string>('')

  const user = isEdit ? mockUsers.find((u) => u.id === editId) : undefined
  const roles = mockRoles

  useEffect(() => {
    if (!open) return
    if (user && isEdit) {
      form.setFieldsValue({
        full_name:  user.full_name,
        username:   user.username,
        email:      user.email,
        phone:      user.phone ?? '',
        status:     user.status === 'ACTIVE',
        role_ids:   user.roles?.[0]?.id ?? undefined,
        send_email: true,
      })
      setAvatarUrl('')
      const roleCode = user.roles?.[0]?.code ?? ''
      setCheckedPerms(ROLE_PERMS[roleCode] ?? [])
    } else {
      form.resetFields()
      form.setFieldsValue({ status: true, send_email: true })
      setAvatarUrl('')
      setCheckedPerms([])
    }
  }, [open, user, isEdit, form])

  const handleRoleChange = (roleId: string) => {
    const role = roles.find((r) => r.id === roleId)
    setCheckedPerms(ROLE_PERMS[role?.code ?? ''] ?? [])
  }

  const fullName = Form.useWatch('full_name', form) ?? ''
  const initials = fullName.split(' ').filter(Boolean).slice(-2).map((w: string) => w[0].toUpperCase()).join('')
  const avatarColor = user?.avatar_color ?? '#00859A'

  const handleSave = (andNew = false) => {
    form.validateFields().then(() => {
      message.success(isEdit ? 'Cập nhật thành công' : 'Thêm người dùng thành công')
      message.info('Đây là giao diện minh hoạ — chưa lưu được thật')
      if (andNew && onSavedAndNew) {
        form.resetFields()
        form.setFieldsValue({ status: true, send_email: true })
        setCheckedPerms([])
        setAvatarUrl('')
        onSavedAndNew()
      } else {
        onClose()
      }
    }).catch(() => {})
  }

  const formTab = (
    <Row gutter={24}>
      {/* ── Left column ── */}
      <Col span={13}>
        <Text strong style={{ fontSize: 13, color: '#0A1D55', display: 'block', marginBottom: 12 }}>
          Thông tin tài khoản
        </Text>

        <Row gutter={12}>
          <Col span={12}>
            <Form.Item name="full_name" label={<>Họ và tên <Text type="danger">*</Text></>}
              rules={[{ required: true, message: 'Bắt buộc nhập họ tên' }]}>
              <Input placeholder="Nhập họ và tên" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="username" label={<>Tên đăng nhập <Text type="danger">*</Text></>}
              rules={[
                { required: true, message: 'Bắt buộc nhập tên đăng nhập' },
                { min: 4, message: 'Tối thiểu 4 ký tự' },
                { pattern: /^[a-z0-9_.]+$/, message: 'Chỉ dùng chữ thường, số, dấu chấm, gạch dưới' },
              ]}>
              <Input placeholder="Nhập tên đăng nhập" disabled={isEdit} />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={12}>
          <Col span={12}>
            <Form.Item name="email" label={<>Email <Text type="danger">*</Text></>}
              rules={[{ required: true }, { type: 'email', message: 'Email không hợp lệ' }]}>
              <Input placeholder="Nhập email" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="phone" label="Số điện thoại">
              <Input placeholder="Nhập số điện thoại" />
            </Form.Item>
          </Col>
        </Row>

        {!isEdit && (
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="password" label={<>Mật khẩu <Text type="danger">*</Text></>} rules={PASSWORD_RULES}>
                <Input.Password placeholder="Nhập mật khẩu" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="confirm_password"
                label={<>Xác nhận mật khẩu <Text type="danger">*</Text></>}
                dependencies={['password']}
                rules={[
                  { required: true, message: 'Vui lòng xác nhận' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue('password') === value) return Promise.resolve()
                      return Promise.reject('Mật khẩu không khớp')
                    },
                  }),
                ]}
              >
                <Input.Password placeholder="Nhập lại mật khẩu" />
              </Form.Item>
            </Col>
          </Row>
        )}

        {/* Avatar upload */}
        <Form.Item label="Ảnh đại diện">
          <AvatarUpload
            initials={initials}
            avatarColor={avatarColor}
            existingUrl={avatarUrl || undefined}
            onUploaded={setAvatarUrl}
          />
        </Form.Item>

        {/* Thông tin bổ sung */}
        <Divider style={{ margin: '12px 0 14px' }} />
        <Text strong style={{ fontSize: 13, color: '#0A1D55', display: 'block', marginBottom: 12 }}>
          Thông tin bổ sung
        </Text>

        <Row gutter={12}>
          <Col span={12}>
            <Form.Item name="title" label="Chức danh">
              <Input placeholder="Nhập chức danh" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="department" label="Phòng ban">
              <Select placeholder="Chọn phòng ban" options={DEPT_OPTIONS} allowClear />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={12}>
          <Col span={12}>
            <Form.Item label="Trạng thái tài khoản">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Form.Item name="status" valuePropName="checked" noStyle>
                  <Switch />
                </Form.Item>
                <Text style={{ fontSize: 13 }}>Kích hoạt</Text>
              </div>
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="expires_at" label="Hết hạn tài khoản">
              <DatePicker style={{ width: '100%' }} placeholder="Chọn ngày hết hạn" format="DD/MM/YYYY" />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item name="send_email" valuePropName="checked" style={{ marginBottom: 0 }}>
          <Checkbox>Gửi email thông báo tài khoản cho người dùng</Checkbox>
        </Form.Item>
      </Col>

      {/* ── Right column: Permissions ── */}
      <Col span={11}>
        <Form.Item
          name="role_ids"
          label={<>Nhóm quyền <Text type="danger">*</Text></>}
          rules={[{ required: true, message: 'Chọn nhóm quyền' }]}
        >
          <Select
            placeholder="Chọn nhóm quyền"
            options={roles.map((r) => ({ value: r.id, label: r.name }))}
            onChange={handleRoleChange}
          />
        </Form.Item>

        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
          Quyền chi tiết (sẽ tự động theo nhóm quyền)
        </Text>
        <div style={{
          border: '1px solid #e5e7eb', borderRadius: 8,
          maxHeight: 380, overflow: 'auto', padding: '4px 0',
        }}>
          <PermTree nodes={PERM_TREE} checked={checkedPerms} onChange={setCheckedPerms} />
        </div>
      </Col>
    </Row>
  )

  const permTab = (
    <div style={{ padding: '8px 0' }}>
      <Text type="secondary" style={{ fontSize: 13, display: 'block', marginBottom: 12 }}>
        Tuỳ chỉnh quyền chi tiết cho người dùng này.
      </Text>
      <div style={{
        border: '1px solid #e5e7eb', borderRadius: 8,
        maxHeight: 460, overflow: 'auto', padding: '4px 0',
      }}>
        <PermTree nodes={PERM_TREE} checked={checkedPerms} onChange={setCheckedPerms} />
      </div>
    </div>
  )

  return (
    <Modal
      open={open}
      onCancel={onClose}
      width={1020}
      title={
        <Text strong style={{ fontSize: 18, color: '#0A1D55' }}>
          {isEdit ? 'Chỉnh sửa người dùng' : 'Thêm mới người dùng'}
        </Text>
      }
      destroyOnClose
      footer={
        <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
          <Button onClick={onClose}>Huỷ</Button>
          {!isEdit && (
            <Button onClick={() => handleSave(true)}>
              Lưu và thêm mới
            </Button>
          )}
          <Button type="primary" onClick={() => handleSave(false)}>
            Lưu
          </Button>
        </Space>
      }
      styles={{ body: { padding: '16px 24px 8px', maxHeight: '78vh', overflow: 'auto' } }}
    >
      <Form form={form} layout="vertical" scrollToFirstError>
        <Tabs
          defaultActiveKey="info"
          style={{ marginBottom: 0 }}
          items={[
            { key: 'info',  label: 'Thông tin người dùng', children: formTab },
            { key: 'perms', label: 'Phân quyền',           children: permTab },
          ]}
        />
      </Form>
    </Modal>
  )
}
