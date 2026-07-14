import { useState, useMemo } from 'react'
import {
  App, Table, Tag, Button, Space, Input, Select, Tooltip,
  Typography, Modal, Form, InputNumber,
  ColorPicker,
} from 'antd'
import {
  PlusOutlined, SearchOutlined, EditOutlined,
  DownloadOutlined, UploadOutlined, ReloadOutlined,
  TagsOutlined, TeamOutlined, GlobalOutlined, KeyOutlined,
  BarChartOutlined, FileTextOutlined, FolderOutlined,
  BellOutlined, BookOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { platforms as mockPlatforms, sourceCategories as mockSourceCategories } from '@/data/mockData'
import EmptyState from '@/components/common/EmptyState'

const { Title, Text } = Typography
const UPDATED_AT = '16/06/2026 10:15'

// ─── Mock data ────────────────────────────────────────────────────────────────
// Chỉ 2 tab có data mẫu thật trong mockData.ts (platforms/sourceCategories) — 7 tab
// còn lại (topic/keyword/attention_level/content_status/case_status/alert_type/
// report_template) không có data mẫu tương ứng, để mảng rỗng + EmptyState (Task 12).
const INIT: Record<string, any[]> = {
  topic: [],
  source_group: mockSourceCategories.map((c, i) => ({
    id: c.id, code: c.code, name: c.name, desc: '', order: i + 1, status: 'ACTIVE', updated_at: UPDATED_AT,
  })),
  platform: mockPlatforms.map((p, i) => ({
    id: p.id, code: p.code, name: p.name, desc: '', order: i + 1, status: 'ACTIVE', updated_at: UPDATED_AT,
  })),
  keyword: [],
  attention_level: [],
  content_status: [],
  case_status: [],
  alert_type: [],
  report_template: [],
}

// ─── Nav config ───────────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { key: 'topic',           icon: <TagsOutlined />,       label: 'Chủ đề',                codeLabel: 'Mã chủ đề',   nameLabel: 'Tên chủ đề' },
  { key: 'source_group',    icon: <TeamOutlined />,        label: 'Nhóm nguồn',            codeLabel: 'Mã nhóm',     nameLabel: 'Tên nhóm nguồn' },
  { key: 'platform',        icon: <GlobalOutlined />,      label: 'Nền tảng',              codeLabel: 'Mã nền tảng', nameLabel: 'Tên nền tảng' },
  { key: 'keyword',         icon: <KeyOutlined />,         label: 'Từ khóa',               codeLabel: 'Mã từ khóa',  nameLabel: 'Từ khóa' },
  { key: 'attention_level', icon: <BarChartOutlined />,    label: 'Mức độ quan tâm',       codeLabel: 'Mã',          nameLabel: 'Tên mức độ' },
  { key: 'content_status',  icon: <FileTextOutlined />,    label: 'Trạng thái nội dung',   codeLabel: 'Mã',          nameLabel: 'Tên trạng thái' },
  { key: 'case_status',     icon: <FolderOutlined />,      label: 'Trạng thái vụ việc',    codeLabel: 'Mã',          nameLabel: 'Tên trạng thái' },
  { key: 'alert_type',      icon: <BellOutlined />,        label: 'Loại cảnh báo',         codeLabel: 'Mã',          nameLabel: 'Tên loại cảnh báo' },
  { key: 'report_template', icon: <BookOutlined />,        label: 'Mẫu báo cáo',           codeLabel: 'Mã mẫu',      nameLabel: 'Tên mẫu báo cáo' },
]

const HAS_COLOR = ['attention_level', 'content_status', 'case_status']
const HAS_SCORE = ['attention_level']

// ─── Status tag ───────────────────────────────────────────────────────────────
function StatusTag({ value }: { value: string }) {
  return value === 'ACTIVE'
    ? <Tag color="success" style={{ borderRadius: 4 }}>Đang sử dụng</Tag>
    : <Tag color="default" style={{ borderRadius: 4 }}>Ngừng sử dụng</Tag>
}

// ─── Row form modal ───────────────────────────────────────────────────────────
function RowModal({
  open, section, initial, onOk, onCancel,
}: { open: boolean; section: typeof NAV_ITEMS[0]; initial: any | null; onOk: (v: any) => void; onCancel: () => void }) {
  const [form] = Form.useForm()
  const hasColor = HAS_COLOR.includes(section.key)
  const hasScore = HAS_SCORE.includes(section.key)

  const handleOk = () => {
    form.validateFields().then(v => {
      const color = hasColor && v.color
        ? (typeof v.color === 'string' ? v.color : v.color.toHexString())
        : undefined
      onOk({ ...v, color })
    })
  }

  const initVals = initial
    ? { ...initial }
    : { status: 'ACTIVE', order: 1 }

  return (
    <Modal
      title={initial ? `Sửa — ${section.label}` : `Thêm mới — ${section.label}`}
      open={open} onOk={handleOk} onCancel={onCancel}
      okText="Lưu" cancelText="Huỷ" width={560}
      afterOpenChange={o => { if (o) form.setFieldsValue(initVals) }}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item name="code" label={section.codeLabel} rules={[{ required: true }]}>
          <Input placeholder="VD: TOPIC_01" style={{ textTransform: 'uppercase' }} />
        </Form.Item>
        <Form.Item name="name" label={section.nameLabel} rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="desc" label="Mô tả">
          <Input.TextArea rows={3} />
        </Form.Item>
        {hasScore && (
          <Form.Item label="Khoảng điểm">
            <Space.Compact>
              <Form.Item name="min_score" noStyle><InputNumber placeholder="Từ" min={0} max={100} /></Form.Item>
              <Input style={{ width: 36, textAlign: 'center', pointerEvents: 'none', background: '#fafafa' }} placeholder="–" disabled />
              <Form.Item name="max_score" noStyle><InputNumber placeholder="Đến" min={0} max={100} /></Form.Item>
            </Space.Compact>
          </Form.Item>
        )}
        {hasColor && (
          <Form.Item name="color" label="Màu sắc">
            <ColorPicker showText format="hex" />
          </Form.Item>
        )}
        <Form.Item name="order" label="Thứ tự">
          <InputNumber min={1} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="status" label="Trạng thái">
          <Select options={[
            { value: 'ACTIVE',   label: 'Đang sử dụng' },
            { value: 'INACTIVE', label: 'Ngừng sử dụng' },
          ]} />
        </Form.Item>
      </Form>
    </Modal>
  )
}

// ─── Section content ──────────────────────────────────────────────────────────
function SectionContent({ section }: { section: typeof NAV_ITEMS[0] }) {
  const { message } = App.useApp()
  const [data, setData] = useState<any[]>(INIT[section.key] ?? [])
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sortOrder, setSortOrder] = useState('asc')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<any | null>(null)

  const filtered = useMemo(() => {
    let list = [...data]
    if (keyword) list = list.filter(r => r.name.toLowerCase().includes(keyword.toLowerCase()) || r.code.toLowerCase().includes(keyword.toLowerCase()))
    if (statusFilter) list = list.filter(r => r.status === statusFilter)
    list.sort((a, b) => sortOrder === 'asc' ? a.order - b.order : b.order - a.order)
    return list
  }, [data, keyword, statusFilter, sortOrder])

  // Lưu/sửa chỉ cập nhật state cục bộ — trang mock thuần, không có backend thật
  const handleSave = (values: any) => {
    const now = dayjs().format('DD/MM/YYYY HH:mm')
    if (editing) {
      setData(prev => prev.map(r => r.id === editing.id ? { ...r, ...values, updated_at: now } : r))
      message.success('Đã cập nhật')
    } else {
      setData(prev => [...prev, { ...values, id: String(Date.now()), updated_at: now }])
      message.success('Đã thêm mới')
    }
    message.info('Đây là giao diện minh hoạ — chưa lưu được thật')
    setModalOpen(false)
    setEditing(null)
  }

  const hasColor = HAS_COLOR.includes(section.key)
  const hasScore = HAS_SCORE.includes(section.key)

  const columns = [
    {
      title: 'STT', width: 56,
      render: (_: any, __: any, i: number) => (
        <Text type="secondary" style={{ fontSize: 13 }}>{i + 1}</Text>
      ),
    },
    {
      title: section.codeLabel, dataIndex: 'code', key: 'code', width: 120,
      render: (v: string) => <Tag style={{ fontFamily: 'monospace', fontSize: 12 }}>{v}</Tag>,
    },
    {
      title: section.nameLabel, dataIndex: 'name', key: 'name',
      render: (v: string) => <Text strong style={{ fontSize: 13 }}>{v}</Text>,
    },
    {
      title: 'Mô tả', dataIndex: 'desc', key: 'desc',
      ellipsis: true,
      render: (v: string) => <Text type="secondary" style={{ fontSize: 13 }}>{v}</Text>,
    },
    ...(hasScore ? [
      { title: 'Điểm min', dataIndex: 'min_score', key: 'min_score', width: 88, render: (v: number) => <Text>{v}</Text> },
      { title: 'Điểm max', dataIndex: 'max_score', key: 'max_score', width: 88, render: (v: number) => <Text>{v}</Text> },
    ] : []),
    ...(hasColor ? [
      {
        title: 'Màu', dataIndex: 'color', key: 'color', width: 80,
        render: (v: string) => (
          <div style={{ width: 28, height: 20, borderRadius: 4, background: v, border: '1px solid #e0e0e0' }} />
        ),
      },
    ] : []),
    {
      title: 'Thứ tự', dataIndex: 'order', key: 'order', width: 72,
      render: (v: number) => <Text style={{ fontSize: 13 }}>{v}</Text>,
    },
    {
      title: 'Trạng thái', dataIndex: 'status', key: 'status', width: 130,
      render: (v: string) => <StatusTag value={v} />,
    },
    {
      title: 'Cập nhật lúc', dataIndex: 'updated_at', key: 'updated_at', width: 140,
      render: (v: string) => <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: 'Thao tác', key: 'actions', width: 56,
      render: (_: any, r: any) => (
        <Tooltip title="Sửa">
          <Button type="text" size="small" icon={<EditOutlined style={{ color: '#1677ff' }} />}
            onClick={() => { setEditing(r); setModalOpen(true) }} />
        </Tooltip>
      ),
    },
  ]

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: '0 0 4px', color: '#0A1D55' }}>
            Danh mục {section.label.toLowerCase()}
          </Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            Quản lý các {section.label.toLowerCase()} dùng chung trong hệ thống.
          </Text>
        </div>
        <Space>
          <Button icon={<DownloadOutlined />}>Xuất Excel</Button>
          <Button icon={<UploadOutlined />}>Nhập Excel</Button>
          <Button type="primary" icon={<PlusOutlined />}
            onClick={() => { setEditing(null); setModalOpen(true) }}>
            Thêm mới
          </Button>
        </Space>
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <Input
          prefix={<SearchOutlined style={{ color: '#8c8c8c' }} />}
          placeholder={`Tìm kiếm theo tên ${section.label.toLowerCase()}...`}
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
            { value: '',         label: 'Trạng thái: Tất cả' },
            { value: 'ACTIVE',   label: 'Đang sử dụng' },
            { value: 'INACTIVE', label: 'Ngừng sử dụng' },
          ]}
        />
        <Select
          value={sortOrder}
          onChange={setSortOrder}
          style={{ width: 200 }}
          options={[
            { value: 'asc',  label: 'Sắp xếp: Thứ tự tăng dần' },
            { value: 'desc', label: 'Sắp xếp: Thứ tự giảm dần' },
          ]}
        />
        <Tooltip title="Làm mới">
          <Button icon={<ReloadOutlined />} onClick={() => { setKeyword(''); setStatusFilter(''); setSortOrder('asc') }} />
        </Tooltip>
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        <Table
          columns={columns}
          dataSource={filtered}
          rowKey="id"
          size="middle"
          scroll={{ x: 900 }}
          locale={{ emptyText: <EmptyState description={`Chưa có dữ liệu mẫu cho ${section.label.toLowerCase()}`} /> }}
          pagination={{
            pageSize: 20,
            showTotal: (total, [s, e]) => `Hiển thị ${s} - ${e} của ${total} bản ghi`,
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '50'],
          }}
        />
      </div>

      <RowModal
        open={modalOpen}
        section={section}
        initial={editing}
        onOk={handleSave}
        onCancel={() => { setModalOpen(false); setEditing(null) }}
      />
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function MasterDataPage() {
  const [activeKey, setActiveKey] = useState('topic')
  const section = NAV_ITEMS.find(n => n.key === activeKey) ?? NAV_ITEMS[0]

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
          <SectionContent key={activeKey} section={section} />
        </div>
      </div>
    </div>
  )
}
