import { useState, useMemo, useEffect, useCallback } from 'react'
import {
  App, Table, Tag, Button, Input, Select, Tooltip,
  Typography, Modal, Form,
} from 'antd'
import {
  PlusOutlined, SearchOutlined, EditOutlined, ReloadOutlined,
  TeamOutlined, KeyOutlined, TagsOutlined,
} from '@ant-design/icons'
import EmptyState from '@/components/common/EmptyState'
import { authFetch } from '@/lib/api'
import PermissionGuard from '@/components/common/PermissionGuard'

const { Title, Text } = Typography

type ApiKeyword = { keyword_id: string; keyword: string; topic_group: string | null; is_active: boolean }
type ApiSourceGroup = { group_id: string; name: string; is_active: boolean }

// Đọc từ GET /api/topic-groups (backend/routers/topic_groups.py) — trả nguyên
// TOPIC_GROUPS trong backend/ai/prompts/v1.py, tránh hardcode trùng lặp ở FE lệch khỏi
// prompt AI đang chạy thật. Chỉ đọc — không có UI tạo/sửa/xóa (xem quyết định không xây
// CRUD cho nhóm chủ đề: rủi ro drift với prompt AI + prompt injection nếu cho nhập free
// text feed thẳng vào AI)
function useTopicGroups() {
  const [topicGroups, setTopicGroups] = useState<string[]>([])
  useEffect(() => {
    authFetch('/api/topic-groups')
      .then(res => (res.ok ? res.json() : { topic_groups: [] }))
      .then(d => setTopicGroups(d.topic_groups ?? []))
      .catch(() => setTopicGroups([]))
  }, [])
  return topicGroups
}

// ─── Nav config ───────────────────────────────────────────────────────────────
// Chỉ còn 3 tab — 6 tab khác (platform/attention_level/content_status/case_status/
// alert_type/report_template) đã gỡ vì không khớp bảng DB thật nào (status Alert/Case là
// enum cứng trong code theo rule 18).
const NAV_ITEMS = [
  { key: 'source_group', icon: <TeamOutlined />, label: 'Nhóm nguồn' },
  { key: 'topic_group', icon: <TagsOutlined />, label: 'Nhóm chủ đề' },
  { key: 'keyword', icon: <KeyOutlined />, label: 'Từ khóa' },
]

// ─── Status tag ───────────────────────────────────────────────────────────────
function StatusTag({ value }: { value: string }) {
  return value === 'ACTIVE'
    ? <Tag color="success" style={{ borderRadius: 4 }}>Đang sử dụng</Tag>
    : <Tag color="default" style={{ borderRadius: 4 }}>Ngừng sử dụng</Tag>
}

// ─── Nhóm nguồn — nối API thật (GET/POST/PUT /api/source-groups) ──────────────
function SourceGroupModal({
  open, initial, onOk, onCancel,
}: { open: boolean; initial: ApiSourceGroup | null; onOk: (v: { name: string; is_active: boolean }) => void; onCancel: () => void }) {
  const [form] = Form.useForm()

  const handleOk = () => {
    form.validateFields().then(v => onOk(v))
  }

  const initVals = initial
    ? { name: initial.name, is_active: initial.is_active }
    : { is_active: true }

  return (
    <Modal
      title={initial ? 'Sửa nhóm nguồn' : 'Thêm nhóm nguồn'}
      open={open} onOk={handleOk} onCancel={onCancel}
      okText="Lưu" cancelText="Huỷ" width={480}
      afterOpenChange={o => { if (o) form.setFieldsValue(initVals) }}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item name="name" label="Tên nhóm nguồn" rules={[{ required: true, message: 'Tên nhóm nguồn không được để trống' }]}>
          <Input placeholder="VD: Chính phủ, Bộ ngành, Báo chí..." />
        </Form.Item>
        <Form.Item name="is_active" label="Trạng thái">
          <Select options={[
            { value: true, label: 'Đang sử dụng' },
            { value: false, label: 'Ngừng sử dụng' },
          ]} />
        </Form.Item>
      </Form>
    </Modal>
  )
}

function SourceGroupSection() {
  const { message } = App.useApp()
  const [data, setData] = useState<ApiSourceGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<ApiSourceGroup | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    authFetch('/api/source-groups?include_inactive=true')
      .then(res => (res.ok ? res.json() : Promise.reject(res)))
      .then(d => setData(d.source_groups ?? []))
      .catch(() => message.error('Không tải được danh sách nhóm nguồn'))
      .finally(() => setLoading(false))
  }, [message])

  useEffect(() => { load() }, [load])

  const filtered = useMemo(() => {
    let list = [...data]
    if (keyword) list = list.filter(r => r.name.toLowerCase().includes(keyword.toLowerCase()))
    if (statusFilter) list = list.filter(r => (statusFilter === 'ACTIVE' ? r.is_active : !r.is_active))
    return list
  }, [data, keyword, statusFilter])

  const handleSave = async (values: { name: string; is_active: boolean }) => {
    try {
      if (editing) {
        const res = await authFetch(`/api/source-groups/${editing.group_id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(values),
        })
        if (!res.ok) throw new Error()
        message.success('Đã cập nhật nhóm nguồn')
      } else {
        const res = await authFetch('/api/source-groups', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: values.name }),
        })
        if (!res.ok) throw new Error()
        message.success('Đã thêm nhóm nguồn')
      }
      setModalOpen(false)
      setEditing(null)
      load()
    } catch {
      message.error('Không lưu được nhóm nguồn')
    }
  }

  const columns = [
    {
      title: 'STT', width: 56,
      render: (_: any, __: any, i: number) => <Text type="secondary" style={{ fontSize: 13 }}>{i + 1}</Text>,
    },
    {
      title: 'Tên nhóm nguồn', dataIndex: 'name', key: 'name',
      render: (v: string) => <Text strong style={{ fontSize: 13 }}>{v}</Text>,
    },
    {
      title: 'Trạng thái', dataIndex: 'is_active', key: 'is_active', width: 130,
      render: (v: boolean) => <StatusTag value={v ? 'ACTIVE' : 'INACTIVE'} />,
    },
    {
      title: 'Thao tác', key: 'actions', width: 90, align: 'center' as const,
      render: (_: any, r: ApiSourceGroup) => (
        <PermissionGuard permission="source.update">
          <Tooltip title="Sửa">
            <Button type="text" size="small" icon={<EditOutlined style={{ color: '#1677ff' }} />}
              onClick={() => { setEditing(r); setModalOpen(true) }} />
          </Tooltip>
        </PermissionGuard>
      ),
    },
  ]

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: '0 0 4px', color: '#0A1D55' }}>Danh mục nhóm nguồn</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            Nhóm nguồn dùng để phân loại Nguồn dữ liệu (VD: Chính phủ, Bộ ngành, Báo chí).
          </Text>
        </div>
        <PermissionGuard permission="source.create">
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); setModalOpen(true) }}>
            Thêm nhóm nguồn
          </Button>
        </PermissionGuard>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <Input
          prefix={<SearchOutlined style={{ color: '#8c8c8c' }} />}
          placeholder="Tìm kiếm nhóm nguồn..."
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          allowClear
          style={{ width: 300 }}
        />
        <Select
          value={statusFilter}
          onChange={setStatusFilter}
          style={{ width: 160 }}
          options={[
            { value: '', label: 'Trạng thái: Tất cả' },
            { value: 'ACTIVE', label: 'Đang sử dụng' },
            { value: 'INACTIVE', label: 'Ngừng sử dụng' },
          ]}
        />
        <Tooltip title="Làm mới">
          <Button icon={<ReloadOutlined />} onClick={load} />
        </Tooltip>
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        <Table
          columns={columns}
          dataSource={filtered}
          rowKey="group_id"
          size="middle"
          loading={loading}
          scroll={{ x: 500 }}
          locale={{ emptyText: <EmptyState description="Chưa có nhóm nguồn nào" /> }}
          pagination={{
            pageSize: 20,
            showTotal: (total, [s, e]) => `Hiển thị ${s} - ${e} của ${total} bản ghi`,
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '50'],
          }}
        />
      </div>

      <SourceGroupModal
        open={modalOpen}
        initial={editing}
        onOk={handleSave}
        onCancel={() => { setModalOpen(false); setEditing(null) }}
      />
    </div>
  )
}

// ─── Từ khóa — nối API thật (GET/POST/PUT /api/keywords) ──────────────────────
function KeywordModal({
  open, initial, topicGroups, onOk, onCancel,
}: {
  open: boolean
  initial: ApiKeyword | null
  topicGroups: string[]
  onOk: (v: { keyword: string; topic_group?: string; is_active: boolean }) => void
  onCancel: () => void
}) {
  const [form] = Form.useForm()

  const handleOk = () => {
    form.validateFields().then(v => onOk(v))
  }

  const initVals = initial
    ? { keyword: initial.keyword, topic_group: initial.topic_group ?? undefined, is_active: initial.is_active }
    : { is_active: true }

  return (
    <Modal
      title={initial ? 'Sửa từ khóa' : 'Thêm từ khóa'}
      open={open} onOk={handleOk} onCancel={onCancel}
      okText="Lưu" cancelText="Huỷ" width={520}
      afterOpenChange={o => { if (o) form.setFieldsValue(initVals) }}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item name="keyword" label="Từ khóa" rules={[{ required: true, message: 'Từ khóa không được để trống' }]}>
          <Input placeholder="VD: tin giả y tế" />
        </Form.Item>
        <Form.Item name="topic_group" label="Nhóm chủ đề">
          <Select allowClear placeholder="Chọn nhóm chủ đề" options={topicGroups.map(t => ({ value: t, label: t }))} />
        </Form.Item>
        <Form.Item name="is_active" label="Trạng thái">
          <Select options={[
            { value: true, label: 'Đang sử dụng' },
            { value: false, label: 'Ngừng sử dụng' },
          ]} />
        </Form.Item>
      </Form>
    </Modal>
  )
}

function KeywordSection() {
  const { message } = App.useApp()
  const topicGroups = useTopicGroups()
  const [data, setData] = useState<ApiKeyword[]>([])
  const [loading, setLoading] = useState(true)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<ApiKeyword | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    authFetch('/api/keywords?include_inactive=true')
      .then(res => (res.ok ? res.json() : Promise.reject(res)))
      .then(d => setData(d.keywords ?? []))
      .catch(() => message.error('Không tải được danh sách từ khóa'))
      .finally(() => setLoading(false))
  }, [message])

  useEffect(() => { load() }, [load])

  const filtered = useMemo(() => {
    let list = [...data]
    if (keyword) list = list.filter(r => r.keyword.toLowerCase().includes(keyword.toLowerCase()))
    if (statusFilter) list = list.filter(r => (statusFilter === 'ACTIVE' ? r.is_active : !r.is_active))
    return list
  }, [data, keyword, statusFilter])

  const handleSave = async (values: { keyword: string; topic_group?: string; is_active: boolean }) => {
    try {
      if (editing) {
        const res = await authFetch(`/api/keywords/${editing.keyword_id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(values),
        })
        if (!res.ok) throw new Error()
        message.success('Đã cập nhật từ khóa')
      } else {
        const res = await authFetch('/api/keywords', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ keyword: values.keyword, topic_group: values.topic_group }),
        })
        if (!res.ok) throw new Error()
        message.success('Đã thêm từ khóa')
      }
      setModalOpen(false)
      setEditing(null)
      load()
    } catch {
      message.error('Không lưu được từ khóa')
    }
  }

  const columns = [
    {
      title: 'STT', width: 56,
      render: (_: any, __: any, i: number) => <Text type="secondary" style={{ fontSize: 13 }}>{i + 1}</Text>,
    },
    {
      title: 'Từ khóa', dataIndex: 'keyword', key: 'keyword',
      render: (v: string) => <Text strong style={{ fontSize: 13 }}>{v}</Text>,
    },
    {
      title: 'Nhóm chủ đề', dataIndex: 'topic_group', key: 'topic_group',
      render: (v: string | null) => v ? <Tag style={{ fontSize: 12 }}>{v}</Tag> : <Text type="secondary">—</Text>,
    },
    {
      title: 'Trạng thái', dataIndex: 'is_active', key: 'is_active', width: 130,
      render: (v: boolean) => <StatusTag value={v ? 'ACTIVE' : 'INACTIVE'} />,
    },
    {
      title: 'Thao tác', key: 'actions', width: 90, align: 'center' as const,
      render: (_: any, r: ApiKeyword) => (
        <PermissionGuard permission="campaign.update">
          <Tooltip title="Sửa">
            <Button type="text" size="small" icon={<EditOutlined style={{ color: '#1677ff' }} />}
              onClick={() => { setEditing(r); setModalOpen(true) }} />
          </Tooltip>
        </PermissionGuard>
      ),
    },
  ]

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: '0 0 4px', color: '#0A1D55' }}>Danh mục từ khóa</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            Từ khóa dùng để lọc phạm vi nội dung cho các Chiến dịch (Campaign).
          </Text>
        </div>
        <PermissionGuard permission="campaign.create">
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); setModalOpen(true) }}>
            Thêm từ khóa
          </Button>
        </PermissionGuard>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <Input
          prefix={<SearchOutlined style={{ color: '#8c8c8c' }} />}
          placeholder="Tìm kiếm từ khóa..."
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          allowClear
          style={{ width: 300 }}
        />
        <Select
          value={statusFilter}
          onChange={setStatusFilter}
          style={{ width: 160 }}
          options={[
            { value: '', label: 'Trạng thái: Tất cả' },
            { value: 'ACTIVE', label: 'Đang sử dụng' },
            { value: 'INACTIVE', label: 'Ngừng sử dụng' },
          ]}
        />
        <Tooltip title="Làm mới">
          <Button icon={<ReloadOutlined />} onClick={load} />
        </Tooltip>
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        <Table
          columns={columns}
          dataSource={filtered}
          rowKey="keyword_id"
          size="middle"
          loading={loading}
          scroll={{ x: 700 }}
          locale={{ emptyText: <EmptyState description="Chưa có từ khóa nào" /> }}
          pagination={{
            pageSize: 20,
            showTotal: (total, [s, e]) => `Hiển thị ${s} - ${e} của ${total} bản ghi`,
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '50'],
          }}
        />
      </div>

      <KeywordModal
        open={modalOpen}
        initial={editing}
        topicGroups={topicGroups}
        onOk={handleSave}
        onCancel={() => { setModalOpen(false); setEditing(null) }}
      />
    </div>
  )
}

// ─── Nhóm chủ đề — CHỈ ĐỌC (GET /api/topic-groups), không có nút Thêm/Sửa/Xóa nào —
// đây là hằng số gắn với prompt AI, không phải danh mục CRUD được (xem comment ở
// useTopicGroups phía trên) ────────────────────────────────────────────────────
function TopicGroupSection() {
  const topicGroups = useTopicGroups()

  const columns = [
    {
      title: 'STT', width: 56,
      render: (_: any, __: any, i: number) => <Text type="secondary" style={{ fontSize: 13 }}>{i + 1}</Text>,
    },
    {
      title: 'Tên nhóm chủ đề', dataIndex: 'name', key: 'name',
      render: (v: string) => <Text strong style={{ fontSize: 13 }}>{v}</Text>,
    },
  ]

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: '0 0 4px', color: '#0A1D55' }}>Danh mục nhóm chủ đề</Title>
        <Text type="secondary" style={{ fontSize: 13 }}>
          Nhóm chủ đề dùng để AI phân loại nội dung — gắn liền với prompt AI đang chạy,
          chỉ xem để biết hệ thống đang phân loại theo những nhóm nào, không chỉnh sửa được qua đây.
        </Text>
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        <Table
          columns={columns}
          dataSource={topicGroups.map((name, i) => ({ name, key: i }))}
          rowKey="key"
          size="middle"
          locale={{ emptyText: <EmptyState description="Chưa tải được danh sách nhóm chủ đề" /> }}
          pagination={false}
        />
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function MasterDataPage() {
  const [activeKey, setActiveKey] = useState('source_group')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 112px)' }}>
      {/* Page title */}
      <div style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0, color: '#0A1D55' }}>Dữ liệu dùng chung</Title>
        <Text type="secondary">Quản lý các danh mục và dữ liệu dùng chung trong hệ thống</Text>
      </div>

      {/* Split layout */}
      <div style={{ display: 'flex', flex: 1, gap: 16, overflow: 'hidden' }}>

        {/* Left nav panel */}
        <div style={{
          width: 220, flexShrink: 0, background: '#fff',
          borderRadius: 12, border: '1px solid #f0f0f0',
          overflow: 'hidden', display: 'flex', flexDirection: 'column',
        }}>
          <div style={{ padding: '16px 20px 12px', borderBottom: '1px solid #f0f0f0' }}>
            <Text strong style={{ fontSize: 14, color: '#0A1D55' }}>Dữ liệu dùng chung</Text>
          </div>
          <div style={{ flex: 1, overflow: 'auto', padding: '8px 0' }}>
            {NAV_ITEMS.map(item => (
              <div
                key={item.key}
                onClick={() => setActiveKey(item.key)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 20px', cursor: 'pointer',
                  background: activeKey === item.key ? '#E6F4F7' : 'transparent',
                  color: activeKey === item.key ? '#00859A' : '#374151',
                  fontWeight: activeKey === item.key ? 600 : 400,
                  borderRight: activeKey === item.key ? '3px solid #00859A' : '3px solid transparent',
                  transition: 'all 0.15s',
                  fontSize: 13,
                }}
              >
                <span style={{ fontSize: 16, color: activeKey === item.key ? '#00859A' : '#8C95A0' }}>
                  {item.icon}
                </span>
                {item.label}
              </div>
            ))}
          </div>
        </div>

        {/* Right content panel */}
        <div style={{
          flex: 1, background: '#fff', borderRadius: 12,
          border: '1px solid #f0f0f0', padding: '20px 24px',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}>
          {activeKey === 'keyword' && <KeywordSection key={activeKey} />}
          {activeKey === 'source_group' && <SourceGroupSection key={activeKey} />}
          {activeKey === 'topic_group' && <TopicGroupSection key={activeKey} />}
        </div>
      </div>
    </div>
  )
}
