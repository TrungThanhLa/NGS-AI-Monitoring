import { Spin } from 'antd'

export default function LoadingState() {
  return (
    <div style={{ padding: '64px 0', textAlign: 'center' }}>
      <Spin size="large" />
    </div>
  )
}
