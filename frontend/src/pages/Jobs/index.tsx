import { useState } from 'react'
import { Card, Table, Tag } from 'antd'
import { jobs as mockJobs } from '@/data/mockData'
import PageHeader from '@/components/common/PageHeader'

const STATUS_COLOR: Record<string, string> = {
  SUCCESS: 'success',
  RUNNING: 'processing',
  FAILED: 'error',
  PENDING: 'default',
}

const STATUS_LABEL: Record<string, string> = {
  SUCCESS: 'Thành công',
  RUNNING: 'Đang chạy',
  FAILED: 'Thất bại',
  PENDING: 'Chờ',
}

export default function JobsPage() {
  const [data] = useState(mockJobs)

  const columns = [
    { title: 'Nguồn dữ liệu', dataIndex: 'source_name', key: 'source_name' },
    {
      title: 'Trạng thái',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => <Tag color={STATUS_COLOR[v]}>{STATUS_LABEL[v]}</Tag>,
    },
    { title: 'Bắt đầu', dataIndex: 'started_at', key: 'started_at' },
    { title: 'Kết thúc', dataIndex: 'finished_at', key: 'finished_at', render: (v: string | null) => v ?? '—' },
    {
      title: 'Bài tìm thấy',
      dataIndex: 'records_found',
      key: 'records_found',
      render: (v: number) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: 'Bài đã lưu',
      dataIndex: 'records_saved',
      key: 'records_saved',
      render: (v: number) => <Tag color="blue">{v}</Tag>,
    },
  ]

  return (
    <div>
      <PageHeader
        title="Lịch chạy & Jobs"
        subtitle="Theo dõi lịch sử thu thập dữ liệu"
        breadcrumbs={[{ title: 'Tổng quan', href: '/' }, { title: 'Lịch chạy & Jobs' }]}
      />

      <Card style={{ borderRadius: 12 }}>
        <Table
          columns={columns}
          dataSource={data}
          rowKey="id"
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  )
}
