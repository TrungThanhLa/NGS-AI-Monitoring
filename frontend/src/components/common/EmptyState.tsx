import { Empty } from 'antd'

interface EmptyStateProps {
  description?: string
}

export default function EmptyState({ description = 'Không có dữ liệu' }: EmptyStateProps) {
  return (
    <div style={{ padding: '48px 0', textAlign: 'center' }}>
      <Empty description={description} />
    </div>
  )
}
