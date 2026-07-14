import { useEffect, useState } from "react";
import { Button, Card, Table, Tag } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import { API_BASE } from "@/lib/api";

type HistoryEntry = {
  report_id: string;
  job_id: string;
  file_path: string;
  created_at: string;
  date_from: string;
  date_to: string;
  job_status: string;
  source_names: string[];
};

export default function ReportsPage() {
  const navigate = useNavigate();
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/reports/history`)
      .then((res) => (res.ok ? res.json() : { history: [] }))
      .then((data) => setHistory(data.history ?? []))
      .catch(() => setHistory([]))
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
            Tạo báo cáo
          </Button>
        }
      />

      <Card style={{ borderRadius: 12 }}>
        <Table<HistoryEntry>
          loading={loading}
          rowKey="report_id"
          dataSource={history}
          locale={{ emptyText: "Chưa có báo cáo nào." }}
          columns={[
            {
              title: "Ngày tạo",
              dataIndex: "created_at",
              render: (v: string) => new Date(v).toLocaleString("vi-VN"),
            },
            { title: "Nguồn", render: (_v, e) => e.source_names.join(", ") || "-" },
            { title: "Khoảng thời gian", render: (_v, e) => `${e.date_from} → ${e.date_to}` },
            {
              title: "Trạng thái",
              dataIndex: "job_status",
              render: (s: string) => <Tag color={s === "completed" ? "green" : "default"}>{s}</Tag>,
            },
            {
              title: "Tải về",
              render: (_v, e) => (
                <Button type="link" href={`${API_BASE}/api/reports/${e.job_id}/download`}>
                  Tải DOCX
                </Button>
              ),
            },
          ]}
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  );
}
