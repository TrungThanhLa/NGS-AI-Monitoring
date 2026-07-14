"use client";

import { useEffect, useState } from "react";
import { Alert, Button, Card, Table, Tag, Tooltip, Typography } from "antd";
import { API_BASE } from "@/lib/api";

type Source = {
  source_id: string;
  name: string;
  domain: string;
  group_name: string;
  // API GET /api/sources chỉ trả về nguồn active (filter_by(is_active=True)) và
  // không có field này trong JSON response — giữ optional để không dùng nhầm
  // như dữ liệu thật, chỉ nguồn tham khảo cho type.
  is_active?: boolean;
};

export default function SourceListPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/sources`)
      .then((res) => (res.ok ? res.json() : { sources: [] }))
      .then((data) => {
        setSources(data.sources ?? []);
        setError(null);
      })
      .catch(() => {
        setSources([]);
        setError("Không tải được danh sách nguồn dữ liệu");
      })
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
        {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
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
              // API GET /api/sources chỉ trả về nguồn active (filter_by(is_active=True))
              // — mọi dòng có mặt trong danh sách đã được đảm bảo là active, không cần
              // (và không có) field is_active thật trong response để đọc.
              render: () => <Tag color="green">Đang hoạt động</Tag>,
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
