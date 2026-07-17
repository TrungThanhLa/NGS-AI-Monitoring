import { useEffect, useState } from 'react'
import { App, Modal, Form, Input, Select, Switch, Row, Col, Typography, Space, Button } from 'antd'
import { authFetch } from '@/lib/api'

const { Text } = Typography

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
            status: u.status === 'ACTIVE',
            role_ids: roleOptions.filter((r) => u.roles.includes(r.code)).map((r) => r.role_id),
          })
        })
        .catch(() => message.error('Không tải được thông tin người dùng'))
    } else {
      form.resetFields()
      form.setFieldsValue({ status: true })
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
            status: values.status ? 'ACTIVE' : 'INACTIVE',
            role_ids: values.role_ids,
          }
        : {
            username: values.username,
            email: values.email,
            full_name: values.full_name,
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

        <Form.Item name="email" label={<>Email <Text type="danger">*</Text></>} rules={[{ required: true }, { type: 'email', message: 'Email không hợp lệ' }]}>
          <Input placeholder="Nhập email" />
        </Form.Item>

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
