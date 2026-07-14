import { useState } from 'react'
import { App, Button, Card, Descriptions, Select, Space } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { alerts as mockAlerts } from '@/data/mockData'
import StatusTag from '@/components/common/StatusTag'
import SeverityTag from '@/components/common/SeverityTag'
import PageHeader from '@/components/common/PageHeader'
import LoadingState from '@/components/common/LoadingState'
import dayjs from 'dayjs'

export default function AlertDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { message } = App.useApp()

  const base = mockAlerts.find((a) => a.id === id)
  const [status, setStatus] = useState(base?.status)

  if (!base) return <LoadingState />

  const data = { ...base, status: status ?? base.status }

  return (
    <div>
      <PageHeader
        title={data.title}
        breadcrumbs={[
          { title: 'Tổng quan', href: '/' },
          { title: 'Cảnh báo', href: '/alerts' },
          { title: 'Chi tiết' },
        ]}
        extra={
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/alerts')}>
              Quay lại
            </Button>
            <Select
              value={data.status}
              onChange={(v) => {
                setStatus(v)
                message.info('Đây là giao diện minh hoạ — chưa lưu được thật')
              }}
              style={{ width: 180 }}
              options={[
                { value: 'IN_PROGRESS', label: 'Xác nhận, đang xử lý' },
                { value: 'RESOLVED', label: 'Đã giải quyết' },
                { value: 'CLOSED', label: 'Đóng' },
              ]}
            />
          </Space>
        }
      />

      <Card style={{ borderRadius: 12 }}>
        <Descriptions column={2} bordered size="small">
          <Descriptions.Item label="Loại cảnh báo">{data.alert_type}</Descriptions.Item>
          <Descriptions.Item label="Mức độ">
            <SeverityTag value={data.severity} />
          </Descriptions.Item>
          <Descriptions.Item label="Trạng thái">
            <StatusTag type="alert" value={data.status} />
          </Descriptions.Item>
          <Descriptions.Item label="Thời gian">
            {dayjs(data.created_at).format('DD/MM/YYYY HH:mm')}
          </Descriptions.Item>
          <Descriptions.Item label="Điểm chú ý">{data.attention_score}</Descriptions.Item>
          <Descriptions.Item label="Người phụ trách">
            {data.assigned_to?.full_name ?? '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Nội dung liên quan" span={2}>
            {data.content_id ? (
              <a onClick={() => navigate(`/contents/${data.content_id}`)}>{data.content_title}</a>
            ) : '—'}
          </Descriptions.Item>
          {data.notes && (
            <Descriptions.Item label="Ghi chú" span={2}>
              {data.notes}
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>
    </div>
  )
}
