import { useEffect, useState } from 'react'
import { App, Modal, Form, InputNumber, Select, Descriptions, Typography } from 'antd'
import dayjs from 'dayjs'
import { authFetch } from '@/lib/api'

const { Text } = Typography

type SourceGroupOption = { group_id: string; name: string; is_active: boolean }

type Source = {
  source_id: string
  name: string
  source_group: string | null
  crawl_frequency: number | null
  status: string | null
  sitemap_url: string | null
  parsing_rules: Record<string, unknown> | null
  last_crawled_at: string | null
  discover_backfilled_from: string | null
}

const formatDate = (v: string | null) => (v ? dayjs(v).format('DD/MM/YYYY HH:mm') : '—')

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
  const [groupOptions, setGroupOptions] = useState<SourceGroupOption[]>([])

  useEffect(() => {
    if (!open) return
    authFetch('/api/source-groups')
      .then(res => (res.ok ? res.json() : { source_groups: [] }))
      .then(d => setGroupOptions(d.source_groups ?? []))
      .catch(() => setGroupOptions([]))
  }, [open])

  useEffect(() => {
    if (source) {
      form.setFieldsValue({
        source_group: source.source_group ?? undefined,
        crawl_frequency_minutes: source.crawl_frequency ? Math.round(source.crawl_frequency / 60) : 30,
        status: source.status ?? 'ACTIVE',
      })
    }
  }, [source, form])

  // Nguồn đã có sẵn source_group không còn active (VD nhóm bị ngừng dùng sau khi gán) vẫn
  // hiện trong dropdown để không mất hiển thị — nhưng chọn lại sẽ bị API từ chối (400)
  const selectOptions = (() => {
    const opts = groupOptions.map(g => ({ value: g.name, label: g.name }))
    if (source?.source_group && !groupOptions.some(g => g.name === source.source_group)) {
      opts.push({ value: source.source_group, label: `${source.source_group} (đã ngừng dùng)` })
    }
    return opts
  })()

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
    <Modal title={`Sửa nguồn: ${source?.name ?? ''}`} open={open} onCancel={onClose} onOk={() => form.submit()} destroyOnClose width={640}>
      <Form form={form} layout="vertical" onFinish={onFinish}>
        <Form.Item name="source_group" label="Nhóm nguồn">
          <Select allowClear placeholder="Chọn nhóm nguồn" options={selectOptions} />
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

      {/* Chỉ đọc — cấu hình crawl (sitemap/parsing_rules) chỉ Admin sửa qua DB (nguyên tắc 7,
          CLAUDE.md), không lộ ra form sửa qua UI này. Đặt sau phần nhập liệu để không cản
          luồng thao tác chính (UX: field sửa được luôn ưu tiên lên trên) */}
      <Descriptions size="small" column={1} bordered style={{ marginTop: 20 }}>
        <Descriptions.Item label="Sitemap URL">
          {source?.sitemap_url ?? <Text type="secondary">—</Text>}
        </Descriptions.Item>
        <Descriptions.Item label="Parsing rules">
          <Text code style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>
            {source?.parsing_rules && Object.keys(source.parsing_rules).length > 0
              ? JSON.stringify(source.parsing_rules, null, 2)
              : '—'}
          </Text>
        </Descriptions.Item>
        <Descriptions.Item label="Lần crawl gần nhất">{formatDate(source?.last_crawled_at ?? null)}</Descriptions.Item>
        <Descriptions.Item label="Đã backfill từ">{formatDate(source?.discover_backfilled_from ?? null)}</Descriptions.Item>
      </Descriptions>
    </Modal>
  )
}
