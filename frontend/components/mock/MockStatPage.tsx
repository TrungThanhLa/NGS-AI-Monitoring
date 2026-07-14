"use client";

import { Card, Col, Row, Statistic, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

export type StatItem = {
  title: string;
  value: number | string;
  suffix?: string;
};

type Props<T extends object> = {
  title: string;
  description?: string;
  stats?: StatItem[];
  columns: ColumnsType<T>;
  dataSource: T[];
  rowKey: keyof T;
};

export default function MockStatPage<T extends object>({
  title,
  description,
  stats,
  columns,
  dataSource,
  rowKey,
}: Props<T>) {
  return (
    <div>
      <Typography.Title level={3}>{title}</Typography.Title>
      {description && (
        <Typography.Paragraph type="secondary">{description}</Typography.Paragraph>
      )}
      {stats && stats.length > 0 && (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          {stats.map((s) => (
            <Col span={24 / stats.length} key={s.title}>
              <Card>
                <Statistic title={s.title} value={s.value} suffix={s.suffix} />
              </Card>
            </Col>
          ))}
        </Row>
      )}
      <Card>
        <Table
          columns={columns}
          dataSource={dataSource}
          rowKey={rowKey as string}
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </div>
  );
}
