import { useEffect } from 'react'
import { App, Modal, Form, Input, InputNumber, Select } from 'antd'
import { authFetch } from '@/lib/api'

type Source = {
  source_id: string
  name: string
  source_group: string | null
  crawl_frequency: number | null
  status: string | null
}

export default function SourceEditModal({
  source, open, onClose, onSaved,
}: {
  source: Source | null
  open: boolean
  onClose: () => void
  onSaved: () => void
}) {
  const { message } = App.useApp()
  const [form] = Form.useForm()

  useEffect(() => {
    if (source) {
      form.setFieldsValue({
        source_group: source.source_group,
        crawl_frequency_minutes: source.crawl_frequency ? Math.round(source.crawl_frequency / 60) : 30,
        status: source.status ?? 'ACTIVE',
      })
    }
  }, [source, form])

  const onFinish = async (values: { source_group?: string; crawl_frequency_minutes: number; status: string }) => {
    if (!source) return
    const res = await authFetch(`/api/sources/${source.source_id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_group: values.source_group,
        crawl_frequency: values.crawl_frequency_minutes * 60,
        status: values.status,
      }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: 'Không thể cập nhật nguồn' }))
      message.error(body.detail ?? 'Không thể cập nhật nguồn')
      return
    }
    message.success('Cập nhật nguồn thành công')
    onSaved()
    onClose()
  }

  return (
    <Modal title={`Sửa nguồn: ${source?.name ?? ''}`} open={open} onCancel={onClose} onOk={() => form.submit()} destroyOnClose>
      <Form form={form} layout="vertical" onFinish={onFinish}>
        <Form.Item name="source_group" label="Nhóm nguồn (Chính phủ/Bộ ngành/Báo chí...)">
          <Input />
        </Form.Item>
        <Form.Item
          name="crawl_frequency_minutes"
          label="Chu kỳ crawl lại (phút)"
          rules={[{ required: true, message: 'Vui lòng nhập chu kỳ crawl' }]}
        >
          <InputNumber min={5} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="status" label="Trạng thái" rules={[{ required: true }]}>
          <Select
            options={[
              { value: 'ACTIVE', label: 'Đang hoạt động' },
              { value: 'INACTIVE', label: 'Tạm dừng' },
            ]}
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}
