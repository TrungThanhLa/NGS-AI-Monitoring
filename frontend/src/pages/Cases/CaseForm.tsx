import { App, Button, Card, Form, Input, Select, Space } from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import { cases as mockCases } from '@/data/mockData'
import PageHeader from '@/components/common/PageHeader'
import { useEffect } from 'react'

export default function CaseForm() {
  const { id } = useParams()
  const isEdit = !!id
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const { message } = App.useApp()

  const caseItem = isEdit ? mockCases.find((c) => c.id === id) : undefined

  useEffect(() => {
    if (caseItem) {
      form.setFieldsValue(caseItem)
    }
  }, [caseItem, form])

  const handleFinish = () => {
    message.info('Đây là giao diện minh hoạ — chưa lưu được thật')
    navigate('/cases')
  }

  return (
    <div>
      <PageHeader
        title={isEdit ? 'Chỉnh sửa vụ việc' : 'Tạo vụ việc mới'}
        breadcrumbs={[
          { title: 'Tổng quan', href: '/' },
          { title: 'Vụ việc', href: '/cases' },
          { title: isEdit ? 'Chỉnh sửa' : 'Tạo mới' },
        ]}
      />

      <Card style={{ borderRadius: 12, maxWidth: 720 }}>
        <Form form={form} layout="vertical" onFinish={handleFinish}>
          <Form.Item name="title" label="Tiêu đề" rules={[{ required: true, message: 'Bắt buộc' }]}>
            <Input placeholder="Tiêu đề vụ việc" />
          </Form.Item>

          <Form.Item name="description" label="Mô tả">
            <Input.TextArea rows={4} placeholder="Mô tả chi tiết vụ việc" />
          </Form.Item>

          <Space style={{ width: '100%' }} align="start">
            <Form.Item
              name="priority"
              label="Mức ưu tiên"
              rules={[{ required: true, message: 'Bắt buộc' }]}
              style={{ flex: 1, minWidth: 160 }}
            >
              <Select
                options={[
                  { value: 'LOW', label: 'Thấp' },
                  { value: 'MEDIUM', label: 'Trung bình' },
                  { value: 'HIGH', label: 'Cao' },
                  { value: 'CRITICAL', label: 'Khẩn cấp' },
                ]}
                placeholder="Chọn mức ưu tiên"
              />
            </Form.Item>
            {isEdit && (
              <Form.Item name="status" label="Trạng thái" style={{ flex: 1, minWidth: 160 }}>
                <Select
                  options={[
                    { value: 'OPEN', label: 'Mở' },
                    { value: 'INVESTIGATING', label: 'Đang điều tra' },
                    { value: 'CONCLUDED', label: 'Đã kết luận' },
                  ]}
                />
              </Form.Item>
            )}
          </Space>

          <Form.Item style={{ marginBottom: 0 }}>
            <Space>
              <Button type="primary" htmlType="submit">
                {isEdit ? 'Lưu thay đổi' : 'Tạo vụ việc'}
              </Button>
              <Button onClick={() => navigate('/cases')}>Hủy</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
