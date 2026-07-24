import { useEffect, useState } from "react";
import { Button, Card, Input, Space, Table, Tag, Tooltip, Typography } from "antd";
import { SearchOutlined, EditOutlined, ApiOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import { authFetch } from "@/lib/api";
import SourceEditModal from "./SourceEditModal";

type Source = {
  source_id: string;
  name: string;
  domain: string;
  group_name: string;
  source_group: string | null;
  crawl_frequency: number | null;
  status: string | null;
  sitemap_url: string | null;
  parsing_rules: Record<string, unknown> | null;
  last_crawled_at: string | null;
  discover_backfilled_from: string | null;
};

export default function SourcesPage() {
  const navigate = useNavigate();
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("");
  const [editingSource, setEditingSource] = useState<Source | null>(null);

  const reload = () => {
    setLoading(true);
    authFetch("/api/sources")
      .then((res) => (res.ok ? res.json() : { sources: [] }))
      .then((data) => {
        setSources(data.sources ?? []);
        setError(null);
      })
      .catch(() => setError("Không tải được danh sách nguồn dữ liệu"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    reload();
  }, []);

  const filtered = sources.filter((s) => s.name.toLowerCase().includes(keyword.toLowerCase()));

  const columns = [
    { title: "Tên nguồn", dataIndex: "name", key: "name", render: (v: string) => <span style={{ fontWeight: 500 }}>{v}</span> },
    { title: "Nhóm nguồn", dataIndex: "group_name", key: "group_name" },
    { title: "Domain", dataIndex: "domain", key: "domain" },
    {
      title: "Trạng thái",
      key: "status",
      render: (_: unknown, r: Source) => {
        const status = r.status ?? "ACTIVE";
        const colorMap: Record<string, string> = {
          ACTIVE: "success",
          INACTIVE: "default",
          ERROR: "error",
        };
        const labelMap: Record<string, string> = {
          ACTIVE: "Đang hoạt động",
          INACTIVE: "Tạm dừng",
          ERROR: "Lỗi",
        };
        return <Tag color={colorMap[status]}>{labelMap[status]}</Tag>;
      },
    },
    {
      title: "Thao tác",
      key: "actions",
      width: 120,
      align: "center" as const,
      render: (_: unknown, r: Source) => (
        <Space>
          <Tooltip title="Chưa triển khai — CRUD nguồn qua UI thuộc phạm vi Slice 6, chưa code">
            <Button type="text" icon={<ApiOutlined />} disabled />
          </Tooltip>
          <Tooltip title="Sửa nhóm nguồn / chu kỳ crawl / trạng thái">
            <Button type="text" icon={<EditOutlined />} onClick={() => setEditingSource(r)} />
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

      <SourceEditModal
        source={editingSource}
        open={editingSource !== null}
        onClose={() => setEditingSource(null)}
        onSaved={reload}
      />
    </div>
  );
}
