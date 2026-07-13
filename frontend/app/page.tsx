"use client";

import { useEffect, useState } from "react";
import SourceSidebar, { SourceItem } from "@/components/SourceSidebar";
import SummaryCard from "@/components/SummaryCard";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
// sessionStorage (không phải localStorage) — chỉ cần sống qua F5 trong cùng tab,
// tự dọn khi đóng tab, tránh "job ma" lưu lại nhiều ngày
const JOB_ID_STORAGE_KEY = "ngs_monitor_job_id";

const DATE_PRESETS = [
  { label: "Hôm nay", days: 0 },
  { label: "7 ngày", days: 7 },
  { label: "30 ngày", days: 30 },
  { label: "90 ngày", days: 90 },
  { label: "150 ngày", days: 150 },
];

function todayMinus(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
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

export default function Home() {
  const [dateFrom, setDateFrom] = useState(todayMinus(7));
  const [dateTo, setDateTo] = useState(todayMinus(0));
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

  const parsedDayCount = Math.round((new Date(dateTo).getTime() - new Date(dateFrom).getTime()) / 86400000);
  // Từ ngày = Đến ngày (VD preset "Hôm nay") vẫn là 1 ngày thực tế, không phải 0
  const dayCount = Number.isFinite(parsedDayCount) ? Math.max(1, parsedDayCount) : 1;

  function updateStatus(data: JobStatus) {
    setStatus(data);
    if (!["pending", "running"].includes(data.status)) {
      sessionStorage.removeItem(JOB_ID_STORAGE_KEY);
    }
  }

  // Khôi phục job đang theo dõi sau khi reload trang (F5) — đọc lại đúng job_id
  // đã lưu trong sessionStorage, hỏi lại /status + /articles để dựng lại đúng
  // UI (bảng crawl, nút Cancel, link download...) như trước khi reload.
  useEffect(() => {
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
  }, []);

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
  }, [jobId, status?.status]);

  async function handleSubmit() {
    setError(null);
    const res = await fetch(`${API_BASE}/api/reports/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_ids: selectedSourceIds, date_from: dateFrom, date_to: dateTo }),
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

  const disabled = !dateFrom || !dateTo || dateFrom > dateTo || selectedSourceIds.length === 0;
  const canCancel = status?.status === "pending" || status?.status === "running";

  return (
    <main className="p-8 max-w-4xl">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">NGS Monitor</h1>
        <a href="/history" className="text-blue-600 underline text-sm">Lịch sử báo cáo</a>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-4">
        <SourceSidebar sources={sources} selectedIds={selectedSourceIds} onToggle={toggleSource} />

        <div>
          <div className="flex gap-2 mb-2">
            {DATE_PRESETS.map((preset) => (
              <button
                key={preset.days}
                className="border rounded px-2 py-1 text-sm"
                onClick={() => applyPreset(preset.days)}
              >
                {preset.label}
              </button>
            ))}
          </div>
          <div className="flex gap-4 mb-3">
            <div>
              <label className="block font-medium">Từ ngày</label>
              <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            </div>
            <div>
              <label className="block font-medium">Đến ngày</label>
              <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </div>
          </div>
          <SummaryCard sourceCount={selectedSourceIds.length} dayCount={dayCount} />
        </div>
      </div>

      <button
        className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
        disabled={disabled}
        onClick={handleSubmit}
      >
        Tạo báo cáo
      </button>

      {error && <p className="text-red-600 mt-4">{error}</p>}

      {status && (
        <div className="mt-6">
          <p>Trạng thái: {status.status}</p>
          <p>
            Đã crawl: {status.progress.crawled} bài — Đã phân tích: {status.progress.analyzed} bài
          </p>
          {canCancel && (
            <button className="bg-red-600 text-white px-3 py-1 rounded mt-2" onClick={handleCancel}>
              Cancel
            </button>
          )}
          {status.status === "completed" && (
            <a className="text-blue-600 underline" href={`${API_BASE}/api/reports/${status.job_id}/download`}>
              Tải báo cáo DOCX
            </a>
          )}
          {status.status === "failed" && <p className="text-red-600">Lỗi: {status.error_log}</p>}
          {status.status === "cancelled" && <p className="text-gray-600">Job đã bị hủy.</p>}
        </div>
      )}

      {articles.length > 0 && (
        <table className="mt-6 w-full text-sm border-collapse">
          <thead>
            <tr className="border-b text-left">
              <th className="p-1">STT</th>
              <th className="p-1">Tiêu đề</th>
              <th className="p-1">Nguồn</th>
              <th className="p-1">Trạng thái</th>
              <th className="p-1">Crawl</th>
              <th className="p-1">Phân tích</th>
              <th className="p-1">Tổng</th>
            </tr>
          </thead>
          <tbody>
            {articles.map((a, index) => (
              <tr key={a.url} className="border-b">
                <td className="p-1">{index + 1}</td>
                <td className="p-1">
                  <a href={a.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">
                    {a.title || a.url}
                  </a>
                </td>
                <td className="p-1">{a.source_name || "-"}</td>
                <td className="p-1">{a.status}</td>
                <td className="p-1">{formatSeconds(a.crawl_duration_seconds)}</td>
                <td className="p-1">{formatSeconds(a.analysis_duration_seconds)}</td>
                <td className="p-1">{formatSeconds(a.total_duration_seconds)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
