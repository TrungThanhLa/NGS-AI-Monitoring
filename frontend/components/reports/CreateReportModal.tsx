"use client";

import { useEffect, useState } from "react";
import { Modal, Button, DatePicker, Space, Table, Tag, Alert, Progress, Popconfirm, Typography } from "antd";
import dayjs, { Dayjs } from "dayjs";
import { API_BASE } from "@/lib/api";
import SourceSidebar, { SourceItem } from "./SourceSidebar";
import SummaryCard from "./SummaryCard";

export const JOB_ID_STORAGE_KEY = "ngs_monitor_job_id";

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

type Props = {
  open: boolean;
  onClose: () => void;
  onCompleted: () => void;
};

export default function CreateReportModal({ open, onClose, onCompleted }: Props) {
  const [dateFrom, setDateFrom] = useState<Dayjs>(todayMinus(7));
  const [dateTo, setDateTo] = useState<Dayjs>(todayMinus(0));
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [articles, setArticles] = useState<CrawledArticle[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/api/sources`)
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

  function updateStatus(data: JobStatus) {
    setStatus(data);
    if (!["pending", "running"].includes(data.status)) {
      sessionStorage.removeItem(JOB_ID_STORAGE_KEY);
      if (data.status === "completed") onCompleted();
    }
  }

  useEffect(() => {
    if (!open) return;
    const savedJobId = sessionStorage.getItem(JOB_ID_STORAGE_KEY);
    if (!savedJobId) return;
    (async () => {
      const [statusRes, articlesRes] = await Promise.all([
        fetch(`${API_BASE}/api/reports/${savedJobId}/status`),
        fetch(`${API_BASE}/api/reports/${savedJobId}/articles`),
      ]);
      if (!statusRes.ok) {
        sessionStorage.removeItem(JOB_ID_STORAGE_KEY);
        return;
      }
      setJobId(savedJobId);
      updateStatus(await statusRes.json());
      if (articlesRes.ok) setArticles((await articlesRes.json()).articles);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    const activeStatuses = ["pending", "running"];
    if (!jobId || !status || !activeStatuses.includes(status.status)) return;
    const interval = setInterval(async () => {
      const [statusRes, articlesRes] = await Promise.all([
        fetch(`${API_BASE}/api/reports/${jobId}/status`),
        fetch(`${API_BASE}/api/reports/${jobId}/articles`),
      ]);
      if (statusRes.ok) updateStatus(await statusRes.json());
      if (articlesRes.ok) setArticles((await articlesRes.json()).articles);
    }, 3000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, status?.status]);

  async function handleSubmit() {
    setError(null);
    const res = await fetch(`${API_BASE}/api/reports/create`, {
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
  }

  async function handleCancel() {
    if (!status) return;
    const res = await fetch(`${API_BASE}/api/reports/${status.job_id}/cancel`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      updateStatus({ ...status, status: data.status });
    }
  }

  const disabled = !dateFrom || !dateTo || dateFrom.isAfter(dateTo) || selectedSourceIds.length === 0;
  const canCancel = status?.status === "pending" || status?.status === "running";
  const progressPercent = status && status.progress.total_estimated > 0
    ? Math.round(((status.progress.crawled + status.progress.analyzed) / (status.progress.total_estimated * 2)) * 100)
    : 0;

  return (
    <Modal open={open} onCancel={onClose} footer={null} width={800} title="Tạo báo cáo">
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

        <Button type="primary" disabled={disabled} onClick={handleSubmit}>
          Tạo báo cáo
        </Button>

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
                <Button type="link" href={`${API_BASE}/api/reports/${status.job_id}/download`}>
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
    </Modal>
  );
}
