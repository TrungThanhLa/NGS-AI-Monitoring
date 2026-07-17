import { useEffect, useState } from "react";
import { Button, Card, DatePicker, Space, Table, Tag, Alert, Progress, Popconfirm, Typography } from "antd";
import dayjs, { Dayjs } from "dayjs";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import PermissionGuard from "@/components/common/PermissionGuard";
import { authFetch } from "@/lib/api";
import SourceSidebar, { SourceItem } from "./SourceSidebar";
import SummaryCard from "./SummaryCard";

const JOB_ID_STORAGE_KEY = "ngs_monitor_job_id";

const DATE_PRESETS = [
  { label: "Hôm nay", days: 0 },
  { label: "7 ngày", days: 7 },
  { label: "30 ngày", days: 30 },
  { label: "90 ngày", days: 90 },
  { label: "150 ngày", days: 150 },
];

function todayMinus(days: number): Dayjs {
  return dayjs().subtract(days, "day");
}

type JobStatus = {
  job_id: string;
  status: string;
  progress: { crawled: number; analyzed: number; total_estimated: number };
  error_log?: string;
};

type CrawledArticle = {
  title: string | null;
  url: string;
  status: string;
  source_name: string | null;
  crawl_duration_seconds: number | null;
  analysis_duration_seconds: number | null;
  total_duration_seconds: number | null;
};

function formatSeconds(value: number | null): string {
  return value === null ? "-" : `${value.toFixed(1)}s`;
}

const statusColor: Record<string, string> = {
  pending: "default",
  running: "blue",
  completed: "green",
  failed: "red",
  cancelled: "default",
};

export default function ReportCreate() {
  const navigate = useNavigate();
  const [dateFrom, setDateFrom] = useState<Dayjs>(todayMinus(7));
  const [dateTo, setDateTo] = useState<Dayjs>(todayMinus(0));
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [articles, setArticles] = useState<CrawledArticle[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    authFetch("/api/sources")
      .then((res) => (res.ok ? res.json() : { sources: [] }))
      .then((data) => setSources(data.sources ?? []))
      .catch(() => setSources([]));
  }, []);

  function toggleSource(sourceId: string) {
    setSelectedSourceIds((prev) =>
      prev.includes(sourceId) ? prev.filter((id) => id !== sourceId) : [...prev, sourceId]
    );
  }

  function applyPreset(days: number) {
    setDateFrom(todayMinus(days));
    setDateTo(todayMinus(0));
  }

  const parsedDayCount = dateTo.diff(dateFrom, "day");
  const dayCount = Number.isFinite(parsedDayCount) ? Math.max(1, parsedDayCount) : 1;

  // Cập nhật status job + tự dọn sessionStorage khi job đã ở trạng thái kết thúc
  // (completed/failed/cancelled) — tránh effect khôi phục F5 tìm lại 1 job đã xong.
  function updateStatus(data: JobStatus) {
    setStatus(data);
    if (!["pending", "running"].includes(data.status)) {
      sessionStorage.removeItem(JOB_ID_STORAGE_KEY);
    }
  }

  // Khôi phục job đang chạy sau F5 — trang này luôn mount ngay khi user vào /reports/create,
  // KHÔNG cần cơ chế "tự mở modal" như bản Next.js (vì đây đã là 1 trang riêng, luôn hiển thị).
  useEffect(() => {
    const savedJobId = sessionStorage.getItem(JOB_ID_STORAGE_KEY);
    if (!savedJobId) return;
    (async () => {
      const [statusRes, articlesRes] = await Promise.all([
        authFetch(`/api/reports/${savedJobId}/status`),
        authFetch(`/api/reports/${savedJobId}/articles`),
      ]);
      if (!statusRes.ok) {
        sessionStorage.removeItem(JOB_ID_STORAGE_KEY);
        return;
      }
      setJobId(savedJobId);
      updateStatus(await statusRes.json());
      if (articlesRes.ok) setArticles((await articlesRes.json()).articles);
    })();
  }, []);

  // Polling mỗi 3 giây khi job đang pending/running — dừng lại (cleanup) ngay khi
  // status đổi sang trạng thái không active (completed/failed/cancelled) nhờ dependency
  // [jobId, status?.status]. Cờ `cancelled` chặn race condition: nếu job bị Cancel
  // (hoặc effect bị cleanup) ngay lúc 1 request poll đang bay, response cũ (mang trạng
  // thái lỗi thời) về sau sẽ bị bỏ qua thay vì ghi đè ngược trạng thái mới hơn.
  useEffect(() => {
    const activeStatuses = ["pending", "running"];
    if (!jobId || !status || !activeStatuses.includes(status.status)) return;
    let cancelled = false;
    const interval = setInterval(async () => {
      const [statusRes, articlesRes] = await Promise.all([
        authFetch(`/api/reports/${jobId}/status`),
        authFetch(`/api/reports/${jobId}/articles`),
      ]);
      if (cancelled) return;
      if (statusRes.ok) updateStatus(await statusRes.json());
      if (articlesRes.ok) setArticles((await articlesRes.json()).articles);
    }, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [jobId, status?.status]);

  // Tạo job báo cáo mới. Chặn double-click bằng `submitting`: job AI chạy CPU-only tốn
  // nhiều phút/bài, bấm trùng sẽ tạo 2 job Celery song song rất lãng phí tài nguyên.
  // Lưu job_id vào sessionStorage để effect khôi phục sau F5 (phía trên) tìm lại được.
  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const res = await authFetch("/api/reports/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_ids: selectedSourceIds,
          date_from: dateFrom.format("YYYY-MM-DD"),
          date_to: dateTo.format("YYYY-MM-DD"),
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || "Tạo báo cáo thất bại");
        return;
      }
      const data = await res.json();
      sessionStorage.setItem(JOB_ID_STORAGE_KEY, data.job_id);
      setJobId(data.job_id);
      setArticles([]);
      updateStatus({ job_id: data.job_id, status: data.status, progress: { crawled: 0, analyzed: 0, total_estimated: 0 } });
    } finally {
      setSubmitting(false);
    }
  }

  // Tải file DOCX qua authFetch (thay vì <a href>) vì endpoint download giờ yêu cầu
  // Bearer token — thẻ <a> thường không gắn được header Authorization khi điều hướng.
  async function handleDownload(jobId: string) {
    const res = await authFetch(`/api/reports/${jobId}/download`);
    if (!res.ok) return;
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${jobId}.docx`;
    link.click();
    window.URL.revokeObjectURL(url);
  }

  // Hủy job đang chạy. Dùng updater callback (setStatus(prev => ...)) thay vì đóng
  // (closure) trực tiếp biến `status` để không vô tình ghi đè bằng snapshot cũ nếu
  // state đã đổi trong lúc chờ response. Báo lỗi rõ ràng khi cancel thất bại (vd job
  // vừa chuyển completed/failed ngay trước đó — backend trả 400) thay vì im lặng bỏ qua.
  async function handleCancel() {
    if (!status) return;
    const res = await authFetch(`/api/reports/${status.job_id}/cancel`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      setStatus((prev) => (prev ? { ...prev, status: data.status } : prev));
      sessionStorage.removeItem(JOB_ID_STORAGE_KEY);
    } else {
      setError("Không thể hủy job — job có thể đã hoàn tất hoặc gặp lỗi trước đó.");
    }
  }

  // `submitting` chỉ đúng trong lúc gọi POST /create (vài trăm ms) — job crawl+AI thật
  // chạy nền 8-13 giây hoặc lâu hơn sau đó, nên phải khóa nút suốt thời gian job còn
  // pending/running (jobActive), không chỉ trong lúc gọi API tạo job. Thiếu điều kiện
  // này cho phép spam click tạo hàng loạt job trùng lặp trong lúc job trước còn chạy.
  const jobActive = status?.status === "pending" || status?.status === "running";
  const disabled =
    !dateFrom || !dateTo || dateFrom.isAfter(dateTo) || selectedSourceIds.length === 0 || jobActive || submitting;
  const canCancel = jobActive;
  const progressPercent = status && status.progress.total_estimated > 0
    ? Math.round(((status.progress.crawled + status.progress.analyzed) / (status.progress.total_estimated * 2)) * 100)
    : 0;

  return (
    <div>
      <PageHeader
        title="Tạo báo cáo mới"
        breadcrumbs={[{ title: "Tổng quan", href: "/" }, { title: "Báo cáo", href: "/reports" }, { title: "Tạo mới" }]}
      />

      <Card style={{ borderRadius: 12 }}>
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <SourceSidebar sources={sources} selectedIds={selectedSourceIds} onToggle={toggleSource} />
            <div>
              <Space style={{ marginBottom: 8 }}>
                {DATE_PRESETS.map((preset) => (
                  <Button key={preset.days} size="small" onClick={() => applyPreset(preset.days)}>
                    {preset.label}
                  </Button>
                ))}
              </Space>
              <Space style={{ display: "flex", marginBottom: 12 }}>
                <div>
                  <Typography.Text>Từ ngày</Typography.Text>
                  <DatePicker value={dateFrom} onChange={(v) => v && setDateFrom(v)} style={{ display: "block" }} />
                </div>
                <div>
                  <Typography.Text>Đến ngày</Typography.Text>
                  <DatePicker value={dateTo} onChange={(v) => v && setDateTo(v)} style={{ display: "block" }} />
                </div>
              </Space>
              <SummaryCard sourceCount={selectedSourceIds.length} dayCount={dayCount} />
            </div>
          </div>

          <Space>
            <PermissionGuard permission="report.create">
              <Button type="primary" disabled={disabled} loading={submitting} onClick={handleSubmit}>
                Tạo báo cáo
              </Button>
            </PermissionGuard>
            <Button onClick={() => navigate("/reports")}>Hủy</Button>
          </Space>

          {error && <Alert type="error" message={error} showIcon />}

          {status && (
            <div>
              <Space align="center">
                <Tag color={statusColor[status.status]}>{status.status}</Tag>
                <Typography.Text>
                  Đã crawl: {status.progress.crawled} bài — Đã phân tích: {status.progress.analyzed} bài
                </Typography.Text>
              </Space>
              <Progress percent={progressPercent} style={{ marginTop: 8 }} />
              <Space style={{ marginTop: 8 }}>
                {canCancel && (
                  <Popconfirm title="Hủy job này?" onConfirm={handleCancel}>
                    <Button danger>Cancel</Button>
                  </Popconfirm>
                )}
                {status.status === "completed" && (
                  <Button type="link" onClick={() => handleDownload(status.job_id)}>
                    Tải báo cáo DOCX
                  </Button>
                )}
              </Space>
              {status.status === "failed" && <Alert style={{ marginTop: 8 }} type="error" message={`Lỗi: ${status.error_log}`} />}
              {status.status === "cancelled" && <Alert style={{ marginTop: 8 }} type="info" message="Job đã bị hủy." />}
            </div>
          )}

          {articles.length > 0 && (
            <Table<CrawledArticle>
              size="small"
              rowKey="url"
              dataSource={articles}
              pagination={{ pageSize: 10 }}
              columns={[
                { title: "STT", render: (_v, _r, index) => index + 1, width: 60 },
                {
                  title: "Tiêu đề",
                  render: (_v, a) => (
                    <a href={a.url} target="_blank" rel="noopener noreferrer">
                      {a.title || a.url}
                    </a>
                  ),
                },
                { title: "Nguồn", render: (_v, a) => a.source_name || "-" },
                { title: "Trạng thái", dataIndex: "status" },
                { title: "Crawl", render: (_v, a) => formatSeconds(a.crawl_duration_seconds) },
                { title: "Phân tích", render: (_v, a) => formatSeconds(a.analysis_duration_seconds) },
                { title: "Tổng", render: (_v, a) => formatSeconds(a.total_duration_seconds) },
              ]}
            />
          )}
        </Space>
      </Card>
    </div>
  );
}
