"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

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

export default function HistoryPage() {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/reports/history`)
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => setHistory(data.history ?? []))
      .catch(() => setError("Không tải được lịch sử báo cáo"));
  }, []);

  return (
    <main className="p-8 max-w-4xl">
      <h1 className="text-2xl font-bold mb-4">Lịch sử báo cáo</h1>

      {error && <p className="text-red-600">{error}</p>}
      {!error && history.length === 0 && <p>Chưa có báo cáo nào.</p>}

      {history.length > 0 && (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b text-left">
              <th className="p-1">Ngày tạo</th>
              <th className="p-1">Nguồn</th>
              <th className="p-1">Khoảng thời gian</th>
              <th className="p-1">Trạng thái</th>
              <th className="p-1">Tải về</th>
            </tr>
          </thead>
          <tbody>
            {history.map((entry) => (
              <tr key={entry.report_id} className="border-b">
                <td className="p-1">{new Date(entry.created_at).toLocaleString("vi-VN")}</td>
                <td className="p-1">{entry.source_names.join(", ") || "-"}</td>
                <td className="p-1">
                  {entry.date_from} → {entry.date_to}
                </td>
                <td className="p-1">{entry.job_status}</td>
                <td className="p-1">
                  <a className="text-blue-600 underline" href={`${API_BASE}/api/reports/${entry.job_id}/download`}>
                    Tải DOCX
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
