"use client";

import { useMemo, useState } from "react";

export type SourceItem = {
  source_id: string;
  name: string;
  domain: string;
  group_name: string;
};

type Props = {
  sources: SourceItem[];
  selectedIds: string[];
  onToggle: (sourceId: string) => void;
};

export default function SourceSidebar({ sources, selectedIds, onToggle }: Props) {
  const [search, setSearch] = useState("");

  // Lọc realtime theo tên nguồn (không phân biệt hoa/thường)
  const filtered = useMemo(
    () => sources.filter((s) => s.name.toLowerCase().includes(search.toLowerCase())),
    [sources, search]
  );

  // Group nguồn đã lọc theo group_name, giữ thứ tự xuất hiện đầu tiên trong `sources`
  const grouped = useMemo(() => {
    const groups = new Map<string, SourceItem[]>();
    for (const source of filtered) {
      const list = groups.get(source.group_name) ?? [];
      list.push(source);
      groups.set(source.group_name, list);
    }
    return Array.from(groups.entries());
  }, [filtered]);

  const selectedSources = sources.filter((s) => selectedIds.includes(s.source_id));

  return (
    <div className="border rounded p-3">
      <input
        type="text"
        placeholder="🔍 Tìm nguồn..."
        className="w-full border rounded px-2 py-1 mb-3"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {selectedSources.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {selectedSources.map((s) => (
            <span key={s.source_id} className="bg-blue-100 text-blue-800 text-sm px-2 py-1 rounded">
              {s.name}{" "}
              <button onClick={() => onToggle(s.source_id)} aria-label={`Bỏ chọn ${s.name}`}>
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {grouped.map(([groupName, items]) => (
        <div key={groupName} className="mb-3">
          <p className="font-medium text-sm text-gray-600 mb-1">{groupName}</p>
          {items.map((source) => (
            <label key={source.source_id} className="flex items-center gap-2 py-0.5 text-sm">
              <input
                type="checkbox"
                checked={selectedIds.includes(source.source_id)}
                onChange={() => onToggle(source.source_id)}
              />
              {source.name}
            </label>
          ))}
        </div>
      ))}

      <p className="text-xs text-gray-500 mt-2">
        {selectedIds.length}/{sources.length} đã chọn
      </p>
    </div>
  );
}
