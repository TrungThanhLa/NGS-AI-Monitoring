import { Tag } from 'antd'

const CAMPAIGN_STATUS: Record<string, { color: string; label: string }> = {
  DRAFT: { color: 'default', label: 'Nháp' },
  ACTIVE: { color: 'success', label: 'Đang hoạt động' },
  PAUSED: { color: 'warning', label: 'Tạm dừng' },
  COMPLETED: { color: 'blue', label: 'Hoàn thành' },
  ARCHIVED: { color: 'default', label: 'Lưu trữ' },
}

const CONTENT_STATUS: Record<string, { color: string; label: string }> = {
  NEW: { color: 'blue', label: 'Mới' },
  PROCESSING: { color: 'processing', label: 'Đang xử lý' },
  REVIEWED: { color: 'cyan', label: 'Đã xem xét' },
  NEED_VERIFY: { color: 'warning', label: 'Cần xác minh' },
  VERIFIED: { color: 'success', label: 'Đã xác minh' },
  NOT_RELEVANT: { color: 'default', label: 'Không liên quan' },
  CASE_CREATED: { color: 'purple', label: 'Đã tạo vụ việc' },
}

const ALERT_STATUS: Record<string, { color: string; label: string }> = {
  NEW: { color: 'error', label: 'Mới' },
  ACKNOWLEDGED: { color: 'warning', label: 'Đã nhận' },
  PROCESSING: { color: 'processing', label: 'Đang xử lý' },
  RESOLVED: { color: 'success', label: 'Đã giải quyết' },
  CLOSED: { color: 'default', label: 'Đã đóng' },
}

const CASE_STATUS: Record<string, { color: string; label: string }> = {
  OPEN: { color: 'error', label: 'Mở' },
  INVESTIGATING: { color: 'processing', label: 'Đang điều tra' },
  RESOLVED: { color: 'success', label: 'Đã giải quyết' },
  CLOSED: { color: 'default', label: 'Đã đóng' },
}

const SENTIMENT: Record<string, { color: string; label: string }> = {
  POSITIVE: { color: 'success', label: 'Tích cực' },
  NEGATIVE: { color: 'error', label: 'Tiêu cực' },
  NEUTRAL: { color: 'default', label: 'Trung lập' },
  MIXED: { color: 'warning', label: 'Hỗn hợp' },
}

const SOURCE_STATUS: Record<string, { color: string; label: string }> = {
  ACTIVE: { color: 'success', label: 'Hoạt động' },
  INACTIVE: { color: 'default', label: 'Không hoạt động' },
  ERROR: { color: 'error', label: 'Lỗi' },
}

const USER_STATUS: Record<string, { color: string; label: string }> = {
  ACTIVE: { color: 'success', label: 'Hoạt động' },
  INACTIVE: { color: 'default', label: 'Không hoạt động' },
  LOCKED: { color: 'error', label: 'Bị khóa' },
}

type StatusType = 'campaign' | 'content' | 'alert' | 'case' | 'sentiment' | 'source' | 'user'

interface StatusTagProps {
  type: StatusType
  value: string
}

const MAP: Record<StatusType, Record<string, { color: string; label: string }>> = {
  campaign: CAMPAIGN_STATUS,
  content: CONTENT_STATUS,
  alert: ALERT_STATUS,
  case: CASE_STATUS,
  sentiment: SENTIMENT,
  source: SOURCE_STATUS,
  user: USER_STATUS,
}

export default function StatusTag({ type, value }: StatusTagProps) {
  const config = MAP[type]?.[value]
  if (!config) return <Tag>{value}</Tag>
  return <Tag color={config.color}>{config.label}</Tag>
}
