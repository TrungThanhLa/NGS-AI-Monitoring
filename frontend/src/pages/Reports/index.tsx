import { useEffect, useState } from "react";
import { Alert, Button, Card, Table, Tag } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import { authFetch } from "@/lib/api";

type HistoryEntry = {
  report_id: string;
  campaign_id: string;
  campaign_name: string;
  format: string;
  status: string;
  created_at: string;
};

export default function ReportsPage() {
  const navigate = useNavigate();
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    authFetch("/api/reports-history")
      .then((res) => {
        if (!res.ok) throw new Error();
        return res.json();
      })
      .then((data) => setHistory(data.history ?? []))
      .catch(() => setError("Không tải được lịch sử báo cáo"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <PageHeader
        title="Báo cáo"
        subtitle="Xem và tải báo cáo giám sát"
        breadcrumbs={[{ title: "Tổng quan", href: "/" }, { title: "Báo cáo" }]}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/reports/create")}>
            Tạo báo cáo nhanh
          </Button>
        }
      />

      <Card style={{ borderRadius: 12 }}>
        {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
        <Table<HistoryEntry>
          loading={loading}
          rowKey="report_id"
          dataSource={history}
          locale={{ emptyText: "Chưa có báo cáo nào." }}
          columns={[
            { title: "Ngày tạo", dataIndex: "created_at", render: (v: string) => new Date(v).toLocaleString("vi-VN") },
            {
              title: "Chiến dịch",
              render: (_v, e) => (
                <a onClick={() => navigate(`/campaigns/${e.campaign_id}`)}>{e.campaign_name}</a>
              ),
            },
            { title: "Định dạng", dataIndex: "format", render: (v: string) => <Tag>{v.toUpperCase()}</Tag> },
            {
              title: "Trạng thái",
              dataIndex: "status",
              render: (s: string) => <Tag color={s === "completed" ? "green" : s === "failed" ? "red" : "blue"}>{s}</Tag>,
            },
          ]}
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  );
}
