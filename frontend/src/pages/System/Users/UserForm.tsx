import { useEffect } from 'react'
import { App, Alert, Button, Card, Col, Divider, Form, Input, Row, Select, Space } from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import { users as mockUsers, roles as mockRoles } from '@/data/mockData'
import PageHeader from '@/components/common/PageHeader'

// BR-1103: password policy
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

export default function UserForm() {
  const { id } = useParams()
  const isEdit = !!id
  const navigate = useNavigate()
  const { message } = App.useApp()
  const [form] = Form.useForm()

  const user = isEdit ? mockUsers.find((u) => u.id === id) : undefined
  const roles = mockRoles

  useEffect(() => {
    if (user) {
      form.setFieldsValue({
        full_name: user.full_name,
        email: user.email,
        phone: user.phone ?? '',
        status: user.status,
        role_ids: user.roles.map((r) => r.id),
      })
    }
  }, [user, form])

  const handleFinish = () => {
    message.info('Đây là giao diện minh hoạ — chưa lưu được thật')
    navigate('/system/users')
  }

  return (
    <div>
      <PageHeader
        title={isEdit ? 'Chỉnh sửa người dùng' : 'Thêm người dùng mới'}
        breadcrumbs={[
          { title: 'Tổng quan', href: '/' },
          { title: 'Người dùng', href: '/system/users' },
          { title: isEdit ? 'Chỉnh sửa' : 'Thêm mới' },
        ]}
      />

      <Card style={{ borderRadius: 12, maxWidth: 720 }}>
        <Form form={form} layout="vertical" onFinish={handleFinish} scrollToFirstError>

          {/* ── Thông tin cơ bản ─────────────────────────────────────────── */}
          <Divider titlePlacement="left" style={{ color: '#1d4e89', fontWeight: 600 }}>
            Thông tin tài khoản
          </Divider>

          {!isEdit && (
            <Form.Item
              name="username"
              label="Tên đăng nhập"
              rules={[
                { required: true, message: 'Bắt buộc nhập tên đăng nhập' },
                { min: 4, message: 'Tối thiểu 4 ký tự' },
                { pattern: /^[a-z0-9_.]+$/, message: 'Chỉ dùng chữ thường, số, dấu chấm, gạch dưới' },
              ]}
            >
              <Input placeholder="vd: nguyen.van.a" autoComplete="off" />
            </Form.Item>
          )}

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="full_name"
                label="Họ và tên"
                rules={[{ required: true, message: 'Bắt buộc nhập họ tên' }]}
              >
                <Input placeholder="Nguyễn Văn A" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="phone" label="Số điện thoại">
                <Input placeholder="0901234567" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="email"
            label="Email"
            rules={[
              { required: true, message: 'Bắt buộc nhập email' },
              { type: 'email', message: 'Địa chỉ email không hợp lệ' },
            ]}
          >
            <Input placeholder="email@example.com" />
          </Form.Item>

          {/* ── Mật khẩu (chỉ khi tạo mới) ──────────────────────────────── */}
          {!isEdit && (
            <>
              <Divider titlePlacement="left" style={{ color: '#1d4e89', fontWeight: 600 }}>
                Mật khẩu
              </Divider>

              <Alert
                type="info"
                showIcon
                message="Yêu cầu mật khẩu: tối thiểu 8 ký tự, có chữ hoa, chữ thường và chữ số."
                style={{ marginBottom: 16, borderRadius: 8 }}
              />

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name="password" label="Mật khẩu" rules={PASSWORD_RULES}>
                    <Input.Password placeholder="Mật khẩu" autoComplete="new-password" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="confirm_password"
                    label="Xác nhận mật khẩu"
                    dependencies={['password']}
                    rules={[
                      { required: true, message: 'Vui lòng xác nhận mật khẩu' },
                      ({ getFieldValue }) => ({
                        validator(_, value) {
                          if (!value || getFieldValue('password') === value) return Promise.resolve()
                          return Promise.reject('Mật khẩu xác nhận không khớp')
                        },
                      }),
                    ]}
                  >
                    <Input.Password placeholder="Nhập lại mật khẩu" autoComplete="new-password" />
                  </Form.Item>
                </Col>
              </Row>
            </>
          )}

          {/* ── Phân quyền ───────────────────────────────────────────────── */}
          <Divider titlePlacement="left" style={{ color: '#1d4e89', fontWeight: 600 }}>
            Vai trò & Trạng thái
          </Divider>

          <Row gutter={16}>
            <Col span={isEdit ? 12 : 24}>
              <Form.Item name="role_ids" label="Vai trò">
                <Select
                  mode="multiple"
                  placeholder="Chọn vai trò..."
                  options={roles.map((r) => ({
                    value: r.id,
                    label: r.name,
                    disabled: r.code === 'ADMIN' && !isEdit,
                  }))}
                  optionFilterProp="label"
                  showSearch
                  allowClear
                />
              </Form.Item>
            </Col>

            {isEdit && (
              <Col span={12}>
                <Form.Item name="status" label="Trạng thái tài khoản">
                  <Select
                    options={[
                      { value: 'ACTIVE',   label: 'Hoạt động' },
                      { value: 'INACTIVE', label: 'Không hoạt động' },
                    ]}
                  />
                </Form.Item>
              </Col>
            )}
          </Row>

          {/* ── Actions ──────────────────────────────────────────────────── */}
          <Form.Item style={{ marginBottom: 0, marginTop: 8 }}>
            <Space>
              <Button type="primary" htmlType="submit">
                {isEdit ? 'Lưu thay đổi' : 'Thêm người dùng'}
              </Button>
              <Button onClick={() => navigate('/system/users')}>Hủy</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
