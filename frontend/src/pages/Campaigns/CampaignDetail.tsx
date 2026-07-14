import { useState } from 'react'
import { Button, Card, Col, Descriptions, Row, Space, Tag, Select, message, Tabs } from 'antd'
import { EditOutlined, ArrowLeftOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { campaigns as mockCampaigns, surveyDetail } from '@/data/mockData'
import StatusTag from '@/components/common/StatusTag'
import PageHeader from '@/components/common/PageHeader'
import LoadingState from '@/components/common/LoadingState'
import dayjs from 'dayjs'

type CampaignStatus = 'DRAFT' | 'ACTIVE' | 'PAUSED' | 'COMPLETED' | 'ARCHIVED'

const STATUS_TRANSITIONS: Record<CampaignStatus, CampaignStatus[]> = {
  DRAFT: ['ACTIVE', 'ARCHIVED'],
  ACTIVE: ['PAUSED', 'COMPLETED', 'ARCHIVED'],
  PAUSED: ['ACTIVE', 'COMPLETED', 'ARCHIVED'],
  COMPLETED: ['ARCHIVED'],
  ARCHIVED: [],
}

const STATUS_LABELS: Record<CampaignStatus, string> = {
  DRAFT: 'Nháp',
  ACTIVE: 'Kích hoạt',
  PAUSED: 'Tạm dừng',
  COMPLETED: 'Hoàn thành',
  ARCHIVED: 'Lưu trữ',
}

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  // surveyDetail có sẵn keywords/sources chi tiết — chỉ campaign đầu tiên (mock) có dữ liệu này,
  // các chiến dịch mock khác trong danh sách chưa có từ khóa/nguồn cụ thể (fallback mảng rỗng)
  const base = id === surveyDetail.id ? surveyDetail : mockCampaigns.find((c) => c.id === id)
  const [status, setStatus] = useState(base?.status)

  if (!base) return <LoadingState />

  const isSurveyDetail = id === surveyDetail.id
  const keywords = isSurveyDetail ? surveyDetail.keywords : []
  const dataSources = isSurveyDetail ? surveyDetail.sources : []
  const data = {
    ...base,
    status: status ?? base.status,
    keywords,
    sources: dataSources,
  }

  const transitions = STATUS_TRANSITIONS[data.status as CampaignStatus] ?? []

  return (
    <div>
      <PageHeader
        title={data.name}
        breadcrumbs={[
          { title: 'Tổng quan', href: '/' },
          { title: 'Chiến dịch giám sát', href: '/campaigns' },
          { title: data.name },
        ]}
        extra={
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/campaigns')}>
              Quay lại
            </Button>
            <Button icon={<EditOutlined />} onClick={() => navigate(`/campaigns/${id}/edit`)}>
              Chỉnh sửa
            </Button>
            {transitions.length > 0 && (
              <Select
                placeholder="Chuyển trạng thái"
                style={{ width: 160 }}
                onChange={(v) => {
                  setStatus(v)
                  message.info('Đây là giao diện minh hoạ — chưa lưu được thật')
                }}
                options={transitions.map((s) => ({ value: s, label: STATUS_LABELS[s] }))}
              />
            )}
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="Thông tin chiến dịch" style={{ borderRadius: 12 }}>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="Mã chiến dịch">
                <Tag>{data.code}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Trạng thái">
                <StatusTag type="campaign" value={data.status} />
              </Descriptions.Item>
              <Descriptions.Item label="Người tạo">{data.owner_name}</Descriptions.Item>
              <Descriptions.Item label="Ngày tạo">
                {dayjs(data.created_at).format('DD/MM/YYYY HH:mm')}
              </Descriptions.Item>
              <Descriptions.Item label="Ngày bắt đầu">
                {data.start_date ? dayjs(data.start_date).format('DD/MM/YYYY') : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Ngày kết thúc">
                {data.end_date ? dayjs(data.end_date).format('DD/MM/YYYY') : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Mô tả" span={2}>
                {data.description ?? '—'}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="Thống kê" style={{ borderRadius: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Từ khóa giám sát</span>
                <Tag color="blue">{data.keywords.length}</Tag>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Nguồn dữ liệu</span>
                <Tag color="green">{data.sources.length}</Tag>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card style={{ borderRadius: 12, marginTop: 16 }}>
        <Tabs
          items={[
            {
              key: 'keywords',
              label: 'Từ khóa giám sát',
              children: (
                <Space wrap>
                  {data.keywords.length > 0
                    ? data.keywords.map((kw) => <Tag key={kw.keyword_id} color="blue">{kw.keyword}</Tag>)
                    : <span style={{ color: '#8c8c8c' }}>Chưa có từ khóa nào</span>}
                </Space>
              ),
            },
            {
              key: 'sources',
              label: 'Nguồn dữ liệu',
              children: (
                <Space wrap>
                  {data.sources.length > 0
                    ? data.sources.map((s) => <Tag key={s.source_id}>{s.source_name}</Tag>)
                    : <span style={{ color: '#8c8c8c' }}>Chưa có nguồn nào</span>}
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}
