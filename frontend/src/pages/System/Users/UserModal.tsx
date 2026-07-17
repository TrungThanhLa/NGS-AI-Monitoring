import { useEffect, useRef, useState } from 'react'
import { App, Modal, Form, Input, Select, Switch, Row, Col, Typography, Space, Button, Avatar } from 'antd'
import { UserOutlined, UploadOutlined } from '@ant-design/icons'
import { authFetch } from '@/lib/api'

const { Text } = Typography

const AVATAR_ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const AVATAR_MAX_SIZE = 2 * 1024 * 1024 // 2MB

// ─── Avatar upload — chỉ khả dụng ở chế độ sửa (cần user_id đã tồn tại) ────────
// Upload ngay khi chọn ảnh, tách khỏi payload JSON chính (multipart riêng)
function AvatarUpload({ userId, avatarUrl }: { userId: string; avatarUrl: string | null }) {
  const { message } = App.useApp()
  const inputRef = useRef<HTMLInputElement>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    if (!avatarUrl) {
      setPreviewUrl(null)
      return
    }
    let objectUrl: string | null = null
    authFetch(avatarUrl)
      .then((res) => (res.ok ? res.blob() : null))
      .then((blob) => {
        if (!blob) return
        objectUrl = URL.createObjectURL(blob)
        setPreviewUrl(objectUrl)
      })
      .catch(() => {})
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [avatarUrl])

  const handleFile = async (file: File) => {
    if (!AVATAR_ALLOWED_TYPES.includes(file.type)) {
      message.error('Chỉ chấp nhận ảnh JPG, PNG hoặc WEBP')
      return
    }
    if (file.size > AVATAR_MAX_SIZE) {
      message.error('Ảnh không được vượt quá 2MB')
      return
    }

    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await authFetch(`/api/users/${userId}/avatar`, { method: 'POST', body: formData })
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: 'Tải ảnh thất bại' }))
        message.error(body.detail ?? 'Tải ảnh thất bại')
        return
      }
      setPreviewUrl(URL.createObjectURL(file))
      message.success('Cập nhật ảnh đại diện thành công')
    } catch {
      message.error('Tải ảnh thất bại — lỗi kết nối')
    } finally {
      setUploading(false)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
      <input ref={inputRef} type="file" accept=".jpg,.jpeg,.png,.webp" style={{ display: 'none' }} onChange={handleInputChange} />
      {previewUrl ? (
        <img src={previewUrl} alt="avatar" style={{ width: 56, height: 56, borderRadius: 8, objectFit: 'cover' }} />
      ) : (
        <Avatar size={56} style={{ background: '#00859A', borderRadius: 8 }} icon={<UserOutlined />} />
      )}
      <Button size="small" icon={<UploadOutlined />} loading={uploading} onClick={() => inputRef.current?.click()}>
        {previewUrl ? 'Thay ảnh' : 'Chọn ảnh'}
      </Button>
      <Text type="secondary" style={{ fontSize: 12 }}>JPG, PNG, WEBP — tối đa 2MB</Text>
    </div>
  )
}

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

type RoleOption = { role_id: string; code: string; name: string }

type UserDetail = {
  user_id: string
  username: string
  full_name: string | null
  email: string | null
  phone: string | null
  avatar_url: string | null
  status: string
  roles: string[]
}

interface Props {
  open: boolean
  editId?: string | null
  onClose: () => void
  onSaved: () => void
}

export default function UserModal({ open, editId, onClose, onSaved }: Props) {
  const isEdit = !!editId
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [roleOptions, setRoleOptions] = useState<RoleOption[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [rolesLoading, setRolesLoading] = useState(false)
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setRolesLoading(true)
    authFetch('/api/roles')
      .then((res) => {
        if (!res.ok) {
          message.error('Không tải được danh sách vai trò')
          return { roles: [] }
        }
        return res.json()
      })
      .then((data) => setRoleOptions(data.roles ?? []))
      .catch(() => message.error('Không tải được danh sách vai trò'))
      .finally(() => setRolesLoading(false))
  }, [open])

  useEffect(() => {
    if (!open) return
    if (isEdit && editId) {
      authFetch(`/api/users/${editId}`)
        .then((res) => res.json())
        .then((u: UserDetail) => {
          form.setFieldsValue({
            full_name: u.full_name,
            username: u.username,
            email: u.email,
            phone: u.phone,
            status: u.status === 'ACTIVE',
            role_ids: roleOptions.filter((r) => u.roles.includes(r.code)).map((r) => r.role_id),
          })
          setAvatarUrl(u.avatar_url)
        })
        .catch(() => message.error('Không tải được thông tin người dùng'))
    } else {
      form.resetFields()
      form.setFieldsValue({ status: true })
      setAvatarUrl(null)
    }
  }, [open, editId, isEdit, form, roleOptions.length])

  const handleSave = async () => {
    let values: Awaited<ReturnType<typeof form.validateFields>>
    try {
      values = await form.validateFields()
    } catch {
      // validateFields() reject — lỗi đã hiện trên form, không cần message thêm
      return
    }

    setSubmitting(true)
    try {
      const payload = isEdit
        ? {
            full_name: values.full_name,
            email: values.email,
            phone: values.phone || null,
            status: values.status ? 'ACTIVE' : 'INACTIVE',
            role_ids: values.role_ids,
          }
        : {
            username: values.username,
            email: values.email,
            full_name: values.full_name,
            phone: values.phone || null,
            password: values.password,
            role_ids: values.role_ids,
          }

      const res = await authFetch(isEdit ? `/api/users/${editId}` : '/api/users', {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: 'Lưu thất bại' }))
        message.error(body.detail ?? 'Lưu thất bại')
        return
      }

      message.success(isEdit ? 'Cập nhật thành công' : 'Thêm người dùng thành công')
      onSaved()
      onClose()
    } catch {
      // authFetch/network lỗi — không phải lỗi validate form
      message.error('Lưu thất bại — lỗi kết nối')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onCancel={onClose}
      width={640}
      title={
        <Text strong style={{ fontSize: 18, color: '#0A1D55' }}>
          {isEdit ? 'Chỉnh sửa người dùng' : 'Thêm mới người dùng'}
        </Text>
      }
      destroyOnClose
      footer={
        <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
          <Button onClick={onClose}>Hủy</Button>
          <Button type="primary" loading={submitting} disabled={rolesLoading} onClick={handleSave}>
            Lưu
          </Button>
        </Space>
      }
    >
      <Form form={form} layout="vertical" scrollToFirstError>
        {isEdit && editId && (
          <Form.Item label="Ảnh đại diện" style={{ marginBottom: 20 }}>
            <AvatarUpload userId={editId} avatarUrl={avatarUrl} />
          </Form.Item>
        )}

        <Row gutter={12}>
          <Col span={12}>
            <Form.Item name="full_name" label={<>Họ và tên <Text type="danger">*</Text></>} rules={[{ required: true, message: 'Bắt buộc nhập họ tên' }]}>
              <Input placeholder="Nhập họ và tên" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              name="username"
              label={<>Tên đăng nhập <Text type="danger">*</Text></>}
              rules={[
                { required: true, message: 'Bắt buộc nhập tên đăng nhập' },
                { min: 4, message: 'Tối thiểu 4 ký tự' },
                { pattern: /^[a-z0-9_.]+$/, message: 'Chỉ dùng chữ thường, số, dấu chấm, gạch dưới' },
              ]}
            >
              <Input placeholder="Nhập tên đăng nhập" disabled={isEdit} />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={12}>
          <Col span={12}>
            <Form.Item name="email" label={<>Email <Text type="danger">*</Text></>} rules={[{ required: true }, { type: 'email', message: 'Email không hợp lệ' }]}>
              <Input placeholder="Nhập email" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              name="phone"
              label="Số điện thoại"
              rules={[{ pattern: /^[0-9+\s-]{8,15}$/, message: 'Số điện thoại không hợp lệ' }]}
            >
              <Input placeholder="Nhập số điện thoại (không bắt buộc)" />
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

        <Form.Item
          name="role_ids"
          label={<>Vai trò <Text type="danger">*</Text></>}
          rules={[{ required: true, message: 'Chọn ít nhất 1 vai trò' }]}
        >
          <Select mode="multiple" placeholder="Chọn vai trò" options={roleOptions.map((r) => ({ value: r.role_id, label: r.name }))} />
        </Form.Item>

        {isEdit && (
          <Form.Item label="Trạng thái tài khoản">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Form.Item name="status" valuePropName="checked" noStyle>
                <Switch />
              </Form.Item>
              <Text style={{ fontSize: 13 }}>Kích hoạt</Text>
            </div>
          </Form.Item>
        )}
      </Form>
    </Modal>
  )
}
