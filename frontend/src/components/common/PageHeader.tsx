import { Breadcrumb, Space, Typography } from 'antd'
import type { ReactNode } from 'react'

interface BreadcrumbItem {
  title: string
  href?: string
}

interface PageHeaderProps {
  title: string
  subtitle?: string
  breadcrumbs?: BreadcrumbItem[]
  extra?: ReactNode
}

export default function PageHeader({ title, subtitle, breadcrumbs, extra }: PageHeaderProps) {
  return (
    <div style={{ marginBottom: 24 }}>
      {breadcrumbs && (
        <Breadcrumb
          style={{ marginBottom: 8 }}
          items={breadcrumbs.map((b) => ({ title: b.href ? <a href={b.href}>{b.title}</a> : b.title }))}
        />
      )}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <Typography.Title level={4} style={{ margin: 0, color: '#0B1F3A' }}>
            {title}
          </Typography.Title>
          {subtitle && (
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
              {subtitle}
            </Typography.Text>
          )}
        </div>
        {extra && <Space>{extra}</Space>}
      </div>
    </div>
  )
}
