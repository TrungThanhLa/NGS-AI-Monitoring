import { useState } from 'react'
import { App, Button, Card, Col, Descriptions, Row, Select, Space, Tag } from 'antd'
import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { cases as mockCases } from '@/data/mockData'
import StatusTag from '@/components/common/StatusTag'
import SeverityTag from '@/components/common/SeverityTag'
import PageHeader from '@/components/common/PageHeader'
import LoadingState from '@/components/common/LoadingState'
import dayjs from 'dayjs'

export default function CaseDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { message } = App.useApp()

  const base = mockCases.find((c) => c.id === id)
  const [status, setStatus] = useState(base?.status)

  if (!base) return <LoadingState />

  const data = { ...base, status: status ?? base.status }

  return (
    <div>
      <PageHeader
        title={`${data.code} — ${data.title}`}
        breadcrumbs={[
          { title: 'Tổng quan', href: '/' },
          { title: 'Vụ việc', href: '/cases' },
          { title: data.code },
        ]}
        extra={
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/cases')}>
              Quay lại
            </Button>
            <Button icon={<EditOutlined />} onClick={() => navigate(`/cases/${id}/edit`)}>
              Chỉnh sửa
            </Button>
            <Select
              value={data.status}
              onChange={(v) => {
                setStatus(v)
                message.info('Đây là giao diện minh hoạ — chưa lưu được thật')
              }}
              style={{ width: 180 }}
              options={[
                { value: 'OPEN', label: 'Mở' },
                { value: 'INVESTIGATING', label: 'Đang điều tra' },
                { value: 'CONCLUDED', label: 'Đã kết luận' },
              ]}
            />
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="Thông tin vụ việc" style={{ borderRadius: 12 }}>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="Mã vụ việc">
                <Tag>{data.code}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Mức ưu tiên">
                <SeverityTag type="priority" value={data.priority} />
              </Descriptions.Item>
              <Descriptions.Item label="Trạng thái">
                <StatusTag type="case" value={data.status} />
              </Descriptions.Item>
              <Descriptions.Item label="Ngày tạo">
                {dayjs(data.created_at).format('DD/MM/YYYY HH:mm')}
              </Descriptions.Item>
              <Descriptions.Item label="Người tạo">{data.created_by?.full_name ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="Người phụ trách">{data.assigned_to?.full_name ?? '—'}</Descriptions.Item>
              {data.closed_at && (
                <Descriptions.Item label="Thời gian đóng" span={2}>
                  {dayjs(data.closed_at).format('DD/MM/YYYY HH:mm')}
                </Descriptions.Item>
              )}
              {data.description && (
                <Descriptions.Item label="Mô tả" span={2}>
                  {data.description}
                </Descriptions.Item>
              )}
            </Descriptions>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="Số liệu liên quan" style={{ borderRadius: 12 }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Số cảnh báo liên quan">{data.alert_count}</Descriptions.Item>
              <Descriptions.Item label="Số nội dung liên quan">{data.content_count}</Descriptions.Item>
              <Descriptions.Item label="Cập nhật lần cuối">
                {dayjs(data.updated_at).format('DD/MM/YYYY HH:mm')}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
