import { useState } from 'react'
import { App, Button, Card, Col, Descriptions, Row, Select, Space, Tag, Typography } from 'antd'
import { ArrowLeftOutlined, LinkOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { contents as mockContents } from '@/data/mockData'
import StatusTag from '@/components/common/StatusTag'
import SeverityTag from '@/components/common/SeverityTag'
import PageHeader from '@/components/common/PageHeader'
import LoadingState from '@/components/common/LoadingState'
import dayjs from 'dayjs'

const REVIEW_OPTIONS = [
  { value: 'REVIEWED', label: 'Đã xem xét' },
  { value: 'NEED_VERIFY', label: 'Cần xác minh' },
  { value: 'VERIFIED', label: 'Đã xác minh' },
  { value: 'NOT_RELEVANT', label: 'Không liên quan' },
  { value: 'CASE_CREATED', label: 'Tạo vụ việc' },
]

export default function ContentDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { message } = App.useApp()

  const base = mockContents.find((c) => c.id === id)
  const [status, setStatus] = useState(base?.status)

  if (!base) return <LoadingState />

  const data = { ...base, status: status ?? base.status }
  const ai = data.ai_analysis

  return (
    <div>
      <PageHeader
        title={data.title}
        breadcrumbs={[
          { title: 'Tổng quan', href: '/' },
          { title: 'Nội dung', href: '/contents' },
          { title: 'Chi tiết' },
        ]}
        extra={
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/contents')}>
              Quay lại
            </Button>
            <Select
              placeholder="Cập nhật trạng thái"
              style={{ width: 180 }}
              onChange={(v) => {
                setStatus(v)
                message.info('Đây là giao diện minh hoạ — chưa lưu được thật')
              }}
              options={REVIEW_OPTIONS}
              value={data.status}
            />
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="Nội dung" style={{ borderRadius: 12 }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="URL">
                <a href={data.url} target="_blank" rel="noopener noreferrer">
                  <LinkOutlined /> {data.url}
                </a>
              </Descriptions.Item>
              <Descriptions.Item label="Nguồn">{data.source?.name ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="Chiến dịch">{data.campaign?.name ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="Ngày đăng">
                {data.published_at ? dayjs(data.published_at).format('DD/MM/YYYY HH:mm') : '—'}
              </Descriptions.Item>
            </Descriptions>

            {data.summary && (
              <div style={{ marginTop: 16 }}>
                <Typography.Text strong>Tóm tắt:</Typography.Text>
                <Typography.Paragraph style={{ marginTop: 8 }}>{data.summary}</Typography.Paragraph>
              </div>
            )}

            {data.content && (
              <div style={{ marginTop: 16 }}>
                <Typography.Text strong>Nội dung đầy đủ:</Typography.Text>
                <Typography.Paragraph
                  style={{ marginTop: 8, whiteSpace: 'pre-wrap', maxHeight: 400, overflow: 'auto' }}
                >
                  {data.content}
                </Typography.Paragraph>
              </div>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="Phân tích AI" style={{ borderRadius: 12, marginBottom: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Cảm xúc:</span>
                {data.sentiment ? <StatusTag type="sentiment" value={data.sentiment} /> : <span>—</span>}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Mức độ chú ý:</span>
                {data.attention_level ? <SeverityTag type="attention" value={data.attention_level} /> : <span>—</span>}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Điểm chú ý:</span>
                <Tag color="blue">{data.attention_score ?? '—'}</Tag>
              </div>
              {ai?.needs_verification && (
                <Tag color="warning">Cần xác minh thêm</Tag>
              )}
            </Space>

            {ai && (
              <>
                {ai.persons?.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>Nhân vật:</Typography.Text>
                    <div style={{ marginTop: 4 }}>
                      {ai.persons.map((p) => <Tag key={p}>{p}</Tag>)}
                    </div>
                  </div>
                )}
                {ai.organizations?.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>Tổ chức:</Typography.Text>
                    <div style={{ marginTop: 4 }}>
                      {ai.organizations.map((o) => <Tag key={o} color="blue">{o}</Tag>)}
                    </div>
                  </div>
                )}
                {ai.locations?.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>Địa điểm:</Typography.Text>
                    <div style={{ marginTop: 4 }}>
                      {ai.locations.map((l) => <Tag key={l} color="green">{l}</Tag>)}
                    </div>
                  </div>
                )}
              </>
            )}
          </Card>

          <Card title="Trạng thái xem xét" style={{ borderRadius: 12 }}>
            <Space direction="vertical">
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span>Trạng thái:</span>
                <StatusTag type="content" value={data.status} />
              </div>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
