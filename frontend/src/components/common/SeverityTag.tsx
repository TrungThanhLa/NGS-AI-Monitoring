import { Tag } from 'antd'

const SEVERITY: Record<string, { color: string; label: string }> = {
  LOW: { color: '#52C41A', label: 'Thấp' },
  MEDIUM: { color: '#FAAD14', label: 'Trung bình' },
  HIGH: { color: '#FA8C16', label: 'Cao' },
  CRITICAL: { color: '#F5222D', label: 'Nghiêm trọng' },
}

const PRIORITY: Record<string, { color: string; label: string }> = {
  LOW: { color: '#52C41A', label: 'Thấp' },
  MEDIUM: { color: '#FAAD14', label: 'Trung bình' },
  HIGH: { color: '#FA8C16', label: 'Cao' },
  CRITICAL: { color: '#F5222D', label: 'Khẩn cấp' },
}

const ATTENTION: Record<string, { color: string; label: string }> = {
  LOW: { color: '#52C41A', label: 'Thấp' },
  MEDIUM: { color: '#FAAD14', label: 'Trung bình' },
  HIGH: { color: '#FA8C16', label: 'Cao' },
  CRITICAL: { color: '#F5222D', label: 'Nguy hiểm' },
}

type SeverityType = 'severity' | 'priority' | 'attention'

interface SeverityTagProps {
  type?: SeverityType
  value: string
}

const MAP: Record<SeverityType, Record<string, { color: string; label: string }>> = {
  severity: SEVERITY,
  priority: PRIORITY,
  attention: ATTENTION,
}

export default function SeverityTag({ type = 'severity', value }: SeverityTagProps) {
  const config = MAP[type]?.[value]
  if (!config) return <Tag>{value}</Tag>
  return (
    <Tag
      style={{
        backgroundColor: config.color + '22',
        borderColor: config.color,
        color: config.color,
        fontWeight: 500,
      }}
    >
      {config.label}
    </Tag>
  )
}
