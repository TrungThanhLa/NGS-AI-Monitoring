import { useEffect, useRef, useState } from 'react'
import { App, Button, Card, Col, DatePicker, Descriptions, Progress, Row, Select, Space, Table, Tag, Tooltip } from 'antd'
import { EditOutlined, ArrowLeftOutlined, PlusOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import StatusTag from '@/components/common/StatusTag'
import PageHeader from '@/components/common/PageHeader'
import LoadingState from '@/components/common/LoadingState'
import PermissionGuard from '@/components/common/PermissionGuard'
import { authFetch } from '@/lib/api'
import dayjs, { Dayjs } from 'dayjs'

type Campaign = {
  campaign_id: string
  code: string | null
  name: string
  description: string | null
  status: string
  mode: string
  start_date: string
  end_date: string | null
  source_ids: string[]
  keyword_ids: string[]
  created_at: string
}

type ReportRow = {
  report_id: string
  format: string
  status: string
  error_log: string | null
  created_at: string
}

type CrawlProgressSourceOneShot = {
  source_id: string
  source_name: string
  total_urls: number | null
  done_urls: number
  status: string
}
type CrawlProgressSourceContinuous = {
  source_id: string
  source_name: string
  last_crawled_at: string | null
  source_status: string
  pending_count: number
  matched_last_24h: number
}
type CrawlProgress =
  | { mode: 'ONE_SHOT'; sources: CrawlProgressSourceOneShot[]; overall_percent: number }
  | { mode: 'CONTINUOUS'; sources: CrawlProgressSourceContinuous[] }

const FORMAT_OPTIONS = [
  { value: 'docx', label: 'Word (.docx)' },
  { value: 'pdf', label: 'PDF' },
  { value: 'xlsx', label: 'Excel (.xlsx)' },
  { value: 'csv', label: 'CSV' },
  { value: 'json', label: 'JSON (raw data)' },
]

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { message } = App.useApp()

  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [reports, setReports] = useState<ReportRow[]>([])
  const [reportRange, setReportRange] = useState<[Dayjs, Dayjs] | null>(null)
  const [reportFormat, setReportFormat] = useState('docx')
  const [creatingReport, setCreatingReport] = useState(false)
  const [crawlProgress, setCrawlProgress] = useState<CrawlProgress | null>(null)
  const hasPrefilledRange = useRef(false)

  function loadCampaign() {
    authFetch(`/api/campaigns/${id}`)
      .then((r) => r.json())
      .then((c: Campaign) => {
        setCampaign(c)
        // Tự điền sẵn khoảng ngày tạo báo cáo theo start_date/end_date của Campaign —
        // chỉ điền 1 lần lúc load đầu, không ghi đè lựa chọn người dùng đã tự đổi sau đó
        // (loadCampaign còn được gọi lại sau Activate/Pause)
        if (!hasPrefilledRange.current) {
          hasPrefilledRange.current = true
          setReportRange([dayjs(c.start_date), c.end_date ? dayjs(c.end_date) : dayjs()])
        }
      })
  }
  function loadReports() {
    authFetch(`/api/campaigns/${id}/reports`).then((r) => r.json()).then((d) => setReports(d.reports ?? []))
  }
  function loadCrawlProgress() {
    authFetch(`/api/campaigns/${id}/crawl-progress`).then((r) => r.json()).then(setCrawlProgress)
  }

  useEffect(() => {
    loadCampaign()
    loadReports()
    loadCrawlProgress()
  }, [id])

  // Polling danh sách report mỗi 3s khi có report đang pending/running — dừng khi
  // không còn report nào ở 2 trạng thái đó (giống pattern polling job cũ, ReportCreate.tsx)
  useEffect(() => {
    const active = reports.some((r) => r.status === 'pending' || r.status === 'running')
    if (!active) return
    const interval = setInterval(loadReports, 3000)
    return () => clearInterval(interval)
  }, [reports])

  // Poll tiến độ crawl VÀ trạng thái Campaign mỗi 3s khi đang ACTIVE — dừng khi
  // COMPLETED/PAUSED/ARCHIVED. Phải poll cả loadCampaign() ở đây (không chỉ
  // loadCrawlProgress()) — nếu không, sau khi crawl xong (chord callback chuyển
  // campaign.status=COMPLETED phía backend), UI vẫn đứng yên với nút "Tạm dừng" hiển
  // thị sai trên 1 Campaign thực ra đã COMPLETED, cho tới khi người dùng tự F5.
  useEffect(() => {
    if (campaign?.status !== 'ACTIVE') return
    const interval = setInterval(() => {
      loadCrawlProgress()
      loadCampaign()
    }, 3000)
    return () => clearInterval(interval)
  }, [campaign?.status])

  if (!campaign) return <LoadingState />

  // Chặn spam "Tạo báo cáo": còn 1 report của campaign này đang pending/running (backend
  // chưa xử lý xong) thì không cho bấm tạo thêm — tránh sinh hàng loạt report trùng
  // date_range/format trong lúc đợi report trước hoàn tất (creatingReport chỉ chặn được
  // đúng khoảnh khắc gọi request, không chặn được việc bấm lại ngay khi request đã xong
  // nhưng report vẫn còn đang chạy nền)
  const hasActiveReport = reports.some((r) => r.status === 'pending' || r.status === 'running')

  async function handleActivate() {
    const res = await authFetch(`/api/campaigns/${id}/activate`, { method: 'POST' })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      message.error(body.detail || 'Kích hoạt thất bại')
      return
    }
    message.success('Đã kích hoạt chiến dịch')
    loadCampaign()
  }

  async function handlePause() {
    const res = await authFetch(`/api/campaigns/${id}/pause`, { method: 'POST' })
    if (res.ok) {
      message.success('Đã tạm dừng chiến dịch')
      loadCampaign()
    }
  }

  async function handleCreateReport() {
    if (!reportRange) return
    setCreatingReport(true)
    try {
      const res = await authFetch(`/api/campaigns/${id}/reports`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date_from: reportRange[0].format('YYYY-MM-DD'),
          date_to: reportRange[1].format('YYYY-MM-DD'),
          format: reportFormat,
        }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        message.error(body.detail || 'Tạo báo cáo thất bại')
        return
      }
      message.success('Đang tạo báo cáo...')
      loadReports()
    } finally {
      setCreatingReport(false)
    }
  }

  async function handleCancelReport(reportId: string) {
    const res = await authFetch(`/api/campaigns/${id}/reports/${reportId}/cancel`, { method: 'POST' })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      message.error(body.detail || 'Hủy báo cáo thất bại')
      return
    }
    message.success('Đã hủy báo cáo')
    loadReports()
  }

  async function handleDownload(reportId: string, format: string) {
    const res = await authFetch(`/api/campaigns/${id}/reports/${reportId}/download`)
    if (!res.ok) return
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${reportId}.${format}`
    link.click()
    window.URL.revokeObjectURL(url)
  }

  return (
    <div>
      <PageHeader
        title={campaign.name}
        breadcrumbs={[
          { title: 'Tổng quan', href: '/' },
          { title: 'Chiến dịch giám sát', href: '/campaigns' },
          { title: campaign.name },
        ]}
        extra={
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/campaigns')}>
              Quay lại
            </Button>
            <Button icon={<EditOutlined />} onClick={() => navigate(`/campaigns/${id}/edit`)}>
              Chỉnh sửa
            </Button>
            {(campaign.status === 'DRAFT' || campaign.status === 'PAUSED') && (
              <PermissionGuard permission="campaign.update">
                <Button type="primary" onClick={handleActivate}>
                  Kích hoạt
                </Button>
              </PermissionGuard>
            )}
            {campaign.status === 'ACTIVE' && (
              <PermissionGuard permission="campaign.update">
                <Button onClick={handlePause}>Tạm dừng</Button>
              </PermissionGuard>
            )}
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="Thông tin chiến dịch" style={{ borderRadius: 12 }}>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="Mã chiến dịch">
                <Tag>{campaign.code ?? '—'}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Trạng thái">
                <StatusTag type="campaign" value={campaign.status} />
              </Descriptions.Item>
              <Descriptions.Item label="Chế độ">{campaign.mode === 'ONE_SHOT' ? 'Tạo báo cáo nhanh' : 'Giám sát liên tục'}</Descriptions.Item>
              <Descriptions.Item label="Ngày tạo">{dayjs(campaign.created_at).format('DD/MM/YYYY HH:mm')}</Descriptions.Item>
              <Descriptions.Item label="Ngày bắt đầu">{dayjs(campaign.start_date).format('DD/MM/YYYY')}</Descriptions.Item>
              <Descriptions.Item label="Ngày kết thúc">{campaign.end_date ? dayjs(campaign.end_date).format('DD/MM/YYYY') : '—'}</Descriptions.Item>
              <Descriptions.Item label="Mô tả" span={2}>{campaign.description ?? '—'}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="Thống kê" style={{ borderRadius: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Từ khóa giám sát</span>
                <Tag color="blue">{campaign.keyword_ids.length}</Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Nguồn dữ liệu</span>
                <Tag color="green">{campaign.source_ids.length}</Tag>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card title="Báo cáo" style={{ borderRadius: 12, marginTop: 16 }}>
        <Space style={{ marginBottom: 16 }} wrap>
          <DatePicker.RangePicker
            value={reportRange}
            onChange={(v) => setReportRange(v as [Dayjs, Dayjs] | null)}
            format="DD/MM/YYYY"
            disabledDate={(current) => {
              if (!current) return false
              if (current.isBefore(dayjs(campaign.start_date), 'day')) return true
              if (campaign.end_date && current.isAfter(dayjs(campaign.end_date), 'day')) return true
              return false
            }}
          />
          <Select value={reportFormat} onChange={setReportFormat} options={FORMAT_OPTIONS} style={{ width: 180 }} />
          <PermissionGuard permission="report.create">
            <Tooltip title={hasActiveReport ? 'Đang có báo cáo khác xử lý — đợi xong rồi tạo tiếp' : undefined}>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                loading={creatingReport}
                disabled={!reportRange || hasActiveReport}
                onClick={handleCreateReport}
              >
                Tạo báo cáo
              </Button>
            </Tooltip>
          </PermissionGuard>
        </Space>

        <Table<ReportRow>
          rowKey="report_id"
          dataSource={reports}
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: 'Chưa có báo cáo nào.' }}
          columns={[
            { title: 'Ngày tạo', dataIndex: 'created_at', render: (v: string) => new Date(v).toLocaleString('vi-VN') },
            { title: 'Định dạng', dataIndex: 'format', render: (v: string) => <Tag>{v.toUpperCase()}</Tag> },
            {
              title: 'Trạng thái',
              dataIndex: 'status',
              render: (s: string, r: ReportRow) => {
                const tag = <Tag color={s === 'completed' ? 'green' : s === 'failed' ? 'red' : 'blue'}>{s}</Tag>
                return s === 'failed' && r.error_log ? <Tooltip title={r.error_log}>{tag}</Tooltip> : tag
              },
            },
            {
              title: 'Tải về',
              render: (_v, r) =>
                r.status === 'completed' ? (
                  <Button type="link" onClick={() => handleDownload(r.report_id, r.format)}>
                    Tải xuống
                  </Button>
                ) : (
                  '-'
                ),
            },
            {
              title: 'Thao tác',
              render: (_v, r) =>
                r.status === 'pending' || r.status === 'running' ? (
                  <PermissionGuard permission="report.create">
                    <Button type="link" danger onClick={() => handleCancelReport(r.report_id)}>
                      Hủy
                    </Button>
                  </PermissionGuard>
                ) : (
                  '-'
                ),
            },
          ]}
        />
      </Card>

      {crawlProgress && (
        <Card title="Tiến độ crawl" style={{ borderRadius: 12, marginTop: 16 }}>
          {crawlProgress.mode === 'ONE_SHOT' ? (
            <Space direction="vertical" style={{ width: '100%' }}>
              <Progress percent={crawlProgress.overall_percent} />
              {crawlProgress.sources.map((s) => (
                <div key={s.source_id} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>{s.source_name}</span>
                  <span>
                    {s.done_urls}/{s.total_urls ?? '…'} ({s.status})
                  </span>
                </div>
              ))}
            </Space>
          ) : (
            <Table
              rowKey="source_id"
              dataSource={crawlProgress.sources}
              pagination={false}
              columns={[
                { title: 'Nguồn', dataIndex: 'source_name' },
                {
                  title: 'Lần crawl gần nhất',
                  dataIndex: 'last_crawled_at',
                  render: (v: string | null) => (v ? new Date(v).toLocaleString('vi-VN') : 'Chưa crawl'),
                },
                { title: 'Bài mới khớp (24h)', dataIndex: 'matched_last_24h' },
                { title: 'Hàng đợi còn lại', dataIndex: 'pending_count' },
              ]}
            />
          )}
        </Card>
      )}
    </div>
  )
}
