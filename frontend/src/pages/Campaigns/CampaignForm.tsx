import { Button, Card, DatePicker, Form, Input, Space, message } from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import { campaigns as mockCampaigns } from '@/data/mockData'
import PageHeader from '@/components/common/PageHeader'
import dayjs from 'dayjs'
import { useEffect } from 'react'

export default function CampaignForm() {
  const { id } = useParams()
  const isEdit = !!id
  const navigate = useNavigate()
  const [form] = Form.useForm()

  const campaign = isEdit ? mockCampaigns.find((c) => c.id === id) : undefined

  useEffect(() => {
    if (campaign) {
      form.setFieldsValue({
        ...campaign,
        start_date: campaign.start_date ? dayjs(campaign.start_date) : null,
        end_date: campaign.end_date ? dayjs(campaign.end_date) : null,
      })
    }
  }, [campaign, form])

  const handleFinish = () => {
    message.info('Đây là giao diện minh hoạ — chưa lưu được thật')
    navigate('/campaigns')
  }

  return (
    <div>
      <PageHeader
        title={isEdit ? 'Chỉnh sửa chiến dịch' : 'Tạo chiến dịch mới'}
        breadcrumbs={[
          { title: 'Tổng quan', href: '/' },
          { title: 'Chiến dịch giám sát', href: '/campaigns' },
          { title: isEdit ? 'Chỉnh sửa' : 'Tạo mới' },
        ]}
      />

      <Card style={{ borderRadius: 12, maxWidth: 720 }}>
        <Form form={form} layout="vertical" onFinish={handleFinish}>
          {!isEdit && (
            <Form.Item
              name="code"
              label="Mã chiến dịch"
              rules={[{ required: true, message: 'Vui lòng nhập mã chiến dịch' }]}
            >
              <Input placeholder="VD: CD-2026-001" />
            </Form.Item>
          )}

          <Form.Item
            name="name"
            label="Tên chiến dịch"
            rules={[{ required: true, message: 'Vui lòng nhập tên chiến dịch' }]}
          >
            <Input placeholder="Nhập tên chiến dịch" />
          </Form.Item>

          <Form.Item name="description" label="Mô tả">
            <Input.TextArea rows={4} placeholder="Mô tả mục tiêu và phạm vi giám sát" />
          </Form.Item>

          <Space style={{ width: '100%' }}>
            <Form.Item name="start_date" label="Ngày bắt đầu" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} format="DD/MM/YYYY" placeholder="Chọn ngày" />
            </Form.Item>
            <Form.Item name="end_date" label="Ngày kết thúc" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} format="DD/MM/YYYY" placeholder="Chọn ngày" />
            </Form.Item>
          </Space>

          <Form.Item style={{ marginBottom: 0 }}>
            <Space>
              <Button type="primary" htmlType="submit">
                {isEdit ? 'Lưu thay đổi' : 'Tạo chiến dịch'}
              </Button>
              <Button onClick={() => navigate('/campaigns')}>Hủy</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
