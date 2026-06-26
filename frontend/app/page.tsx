"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
// UUID cố định seed sẵn cho nguồn VTV ở migration 0002_seed_vtv_source.py
const VTV_SOURCE_ID = "00000000-0000-0000-0000-000000000001";

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
  title: string;
  url: string;
  status: string;
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

  useEffect(() => {
    const activeStatuses = ["pending", "running"];
    if (!jobId || !status || !activeStatuses.includes(status.status)) return;
    const interval = setInterval(async () => {
      const [statusRes, articlesRes] = await Promise.all([
        fetch(`${API_BASE}/api/reports/${jobId}/status`),
        fetch(`${API_BASE}/api/reports/${jobId}/articles`),
      ]);
      if (statusRes.ok) setStatus(await statusRes.json());
      if (articlesRes.ok) setArticles((await articlesRes.json()).articles);
    }, 3000);
    return () => clearInterval(interval);
  }, [jobId, status?.status]);

  async function handleSubmit() {
    setError(null);
    const res = await fetch(`${API_BASE}/api/reports/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_ids: [VTV_SOURCE_ID], date_from: dateFrom, date_to: dateTo }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Tạo báo cáo thất bại");
      return;
    }
    const data = await res.json();
    setJobId(data.job_id);
    setArticles([]);
    setStatus({ job_id: data.job_id, status: data.status, progress: { crawled: 0, analyzed: 0, total_estimated: 0 } });
  }

  async function handleCancel() {
    if (!status) return;
    const res = await fetch(`${API_BASE}/api/reports/${status.job_id}/cancel`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      setStatus({ ...status, status: data.status });
    }
  }

  const disabled = !dateFrom || !dateTo || dateFrom >= dateTo;
  const canCancel = status?.status === "pending" || status?.status === "running";

  return (
    <main className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold mb-4">NGS Monitor</h1>

      <div className="mb-4">
        <label className="block font-medium">Nguồn dữ liệu</label>
        <p>VTV News</p>
      </div>

      <div className="mb-4 flex gap-4">
        <div>
          <label className="block font-medium">Từ ngày</label>
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div>
          <label className="block font-medium">Đến ngày</label>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
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
              <th className="p-1">Tiêu đề</th>
              <th className="p-1">Trạng thái</th>
              <th className="p-1">Crawl</th>
              <th className="p-1">Phân tích</th>
              <th className="p-1">Tổng</th>
            </tr>
          </thead>
          <tbody>
            {articles.map((a) => (
              <tr key={a.url} className="border-b">
                <td className="p-1">
                  <a href={a.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">
                    {a.title}
                  </a>
                </td>
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
