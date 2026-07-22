import { App, Button, Card, DatePicker, Form, Input, Radio, Select, Space } from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import PageHeader from '@/components/common/PageHeader'
import { authFetch } from '@/lib/api'
import { useAuth } from '@/lib/AuthContext'
import dayjs from 'dayjs'
import { useEffect, useState } from 'react'

type SourceOption = { source_id: string; name: string; source_group: string | null }
type KeywordOption = { keyword_id: string; keyword: string }

export default function CampaignForm() {
  const { id } = useParams()
  const isEdit = !!id
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const { user } = useAuth()

  const [sources, setSources] = useState<SourceOption[]>([])
  const [keywords, setKeywords] = useState<KeywordOption[]>([])
  const [loading, setLoading] = useState(isEdit)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    authFetch('/api/sources').then((r) => r.json()).then((d) => setSources(d.sources ?? []))
    authFetch('/api/keywords').then((r) => r.json()).then((d) => setKeywords(d.keywords ?? []))
  }, [])

  useEffect(() => {
    if (!isEdit) return
    authFetch(`/api/campaigns/${id}`)
      .then((r) => r.json())
      .then((c) =>
        form.setFieldsValue({
          name: c.name,
          description: c.description,
          objective: c.objective,
          mode: c.mode,
          start_date: c.start_date ? dayjs(c.start_date) : null,
          end_date: c.end_date ? dayjs(c.end_date) : null,
          source_ids: c.source_ids,
          keyword_ids: c.keyword_ids,
        })
      )
      .finally(() => setLoading(false))
  }, [id, isEdit, form])

  async function handleFinish(values: any) {
    setSubmitting(true)
    try {
      const payload: Record<string, unknown> = {
        name: values.name,
        description: values.description,
        objective: values.objective,
        mode: values.mode,
        start_date: values.start_date.format('YYYY-MM-DD'),
        end_date: values.end_date ? values.end_date.format('YYYY-MM-DD') : null,
        source_ids: values.source_ids ?? [],
        keyword_ids: values.keyword_ids ?? [],
      }
      // owner_id chỉ bắt buộc lúc tạo mới (BR-CAMP-01) — PUT không nhận field này,
      // gán chủ chiến dịch không đổi khi sửa
      if (!isEdit) payload.owner_id = user?.user_id

      const res = await authFetch(isEdit ? `/api/campaigns/${id}` : '/api/campaigns', {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        message.error(body.detail || 'Lưu chiến dịch thất bại')
        return
      }
      message.success(isEdit ? 'Đã cập nhật chiến dịch' : 'Đã tạo chiến dịch (trạng thái Nháp)')
      const saved = await res.json()
      navigate(`/campaigns/${saved.campaign_id}`)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return null

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
        <Form form={form} layout="vertical" onFinish={handleFinish} initialValues={{ mode: 'CONTINUOUS' }}>
          <Form.Item name="name" label="Tên chiến dịch" rules={[{ required: true, message: 'Vui lòng nhập tên chiến dịch' }]}>
            <Input placeholder="Nhập tên chiến dịch" />
          </Form.Item>

          <Form.Item name="description" label="Mô tả">
            <Input.TextArea rows={3} placeholder="Mô tả mục tiêu và phạm vi giám sát" />
          </Form.Item>

          <Form.Item name="objective" label="Mục tiêu">
            <Input.TextArea rows={2} placeholder="Mục tiêu giám sát" />
          </Form.Item>

          <Form.Item name="mode" label="Chế độ">
            <Radio.Group>
              <Radio.Button value="CONTINUOUS">Giám sát liên tục</Radio.Button>
              <Radio.Button value="ONE_SHOT">Tạo báo cáo nhanh (1 lần)</Radio.Button>
            </Radio.Group>
          </Form.Item>

          <Space style={{ width: '100%' }}>
            <Form.Item name="start_date" label="Ngày bắt đầu" style={{ flex: 1 }} rules={[{ required: true, message: 'Bắt buộc' }]}>
              <DatePicker style={{ width: '100%' }} format="DD/MM/YYYY" />
            </Form.Item>
            <Form.Item name="end_date" label="Ngày kết thúc" style={{ flex: 1 }}>
              <DatePicker style={{ width: '100%' }} format="DD/MM/YYYY" />
            </Form.Item>
          </Space>

          <Form.Item name="source_ids" label="Nguồn dữ liệu" extra="Cần ít nhất 1 nguồn để kích hoạt (BR-CAMP-03)">
            <Select
              mode="multiple"
              placeholder="Chọn nguồn"
              options={sources.map((s) => ({ value: s.source_id, label: `${s.name}${s.source_group ? ` (${s.source_group})` : ''}` }))}
            />
          </Form.Item>

          <Form.Item name="keyword_ids" label="Từ khóa giám sát" extra="Cần ít nhất 1 từ khóa để kích hoạt (BR-CAMP-03)">
            <Select mode="multiple" placeholder="Chọn từ khóa" options={keywords.map((k) => ({ value: k.keyword_id, label: k.keyword }))} />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0 }}>
            <Space>
              <Button type="primary" htmlType="submit" loading={submitting}>
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
