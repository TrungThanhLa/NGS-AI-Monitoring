import { useEffect, useState } from "react";
import { Button, Card, Input, Space, Table, Tag, Tooltip, Typography } from "antd";
import { SearchOutlined, EditOutlined, ApiOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import { authFetch } from "@/lib/api";

type Source = {
  source_id: string;
  name: string;
  domain: string;
  group_name: string;
};

export default function SourcesPage() {
  const navigate = useNavigate();
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("");

  useEffect(() => {
    authFetch("/api/sources")
      .then((res) => (res.ok ? res.json() : { sources: [] }))
      .then((data) => {
        setSources(data.sources ?? []);
        setError(null);
      })
      .catch(() => setError("Không tải được danh sách nguồn dữ liệu"))
      .finally(() => setLoading(false));
  }, []);

  const filtered = sources.filter((s) => s.name.toLowerCase().includes(keyword.toLowerCase()));

  const columns = [
    { title: "Tên nguồn", dataIndex: "name", key: "name", render: (v: string) => <span style={{ fontWeight: 500 }}>{v}</span> },
    { title: "Nhóm nguồn", dataIndex: "group_name", key: "group_name" },
    { title: "Domain", dataIndex: "domain", key: "domain" },
    {
      title: "Trạng thái",
      key: "status",
      render: () => <Tag color="success">Đang hoạt động</Tag>,
    },
    {
      title: "Thao tác",
      key: "actions",
      width: 140,
      render: (_: unknown, r: Source) => (
        <Space>
          <Tooltip title="Chưa triển khai — CRUD nguồn qua UI thuộc phạm vi Slice 6, chưa code">
            <Button type="text" icon={<ApiOutlined />} disabled />
          </Tooltip>
          <Tooltip title="Chưa triển khai">
            <Button type="text" icon={<EditOutlined />} disabled />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Nguồn dữ liệu"
        subtitle="Danh sách nguồn thu thập thông tin"
        breadcrumbs={[{ title: "Tổng quan", href: "/" }, { title: "Nguồn dữ liệu" }]}
      />

      {error && (
        <Typography.Text type="danger" style={{ display: "block", marginBottom: 16 }}>
          {error}
        </Typography.Text>
      )}

      <Card style={{ borderRadius: 12 }}>
        <Space style={{ marginBottom: 16 }}>
          <Input
            placeholder="Tìm kiếm nguồn..."
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 280 }}
            allowClear
          />
        </Space>

        <Table
          columns={columns}
          dataSource={filtered}
          rowKey="source_id"
          loading={loading}
          pagination={{ pageSize: 20, showTotal: (t) => `Tổng ${t} nguồn` }}
        />
      </Card>
    </div>
  );
}
