"use client";

import { useEffect, useState } from "react";
import { Button, Card, Table, Tag, Tooltip, Typography } from "antd";
import { API_BASE } from "@/lib/api";

type Source = {
  source_id: string;
  name: string;
  domain: string;
  group_name: string;
  is_active: boolean;
};

export default function SourceListPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/sources`)
      .then((res) => (res.ok ? res.json() : { sources: [] }))
      .then((data) => setSources(data.sources ?? []))
      .catch(() => setSources([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <Typography.Title level={3}>Nguồn dữ liệu</Typography.Title>
      <Card
        extra={
          <Tooltip title="Chưa triển khai — CRUD nguồn qua UI thuộc phạm vi Slice 6, chưa code">
            <Button type="primary" disabled>
              Thêm nguồn
            </Button>
          </Tooltip>
        }
      >
        <Table<Source>
          loading={loading}
          rowKey="source_id"
          dataSource={sources}
          columns={[
            { title: "Tên nguồn", dataIndex: "name" },
            { title: "Nhóm nguồn", dataIndex: "group_name" },
            { title: "Domain", dataIndex: "domain" },
            {
              title: "Trạng thái",
              dataIndex: "is_active",
              render: (active: boolean) => <Tag color={active ? "green" : "default"}>{active ? "Đang hoạt động" : "Tắt"}</Tag>,
            },
            {
              title: "Hành động",
              render: () => (
                <Tooltip title="Chưa triển khai">
                  <Button size="small" disabled>
                    Sửa
                  </Button>
                </Tooltip>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
