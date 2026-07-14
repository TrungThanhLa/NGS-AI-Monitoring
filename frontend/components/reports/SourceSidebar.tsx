"use client";

import { useMemo, useState } from "react";
import { Input, Checkbox, Tag, Typography } from "antd";
import { SearchOutlined, CloseOutlined } from "@ant-design/icons";

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

  const filtered = useMemo(
    () => sources.filter((s) => s.name.toLowerCase().includes(search.toLowerCase())),
    [sources, search]
  );

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
    <div style={{ border: "1px solid #f0f0f0", borderRadius: 8, padding: 12 }}>
      <Input
        prefix={<SearchOutlined />}
        placeholder="Tìm nguồn..."
        aria-label="Tìm nguồn"
        style={{ marginBottom: 12 }}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {selectedSources.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          {selectedSources.map((s) => (
            <Tag
              key={s.source_id}
              closable
              onClose={() => onToggle(s.source_id)}
              color="blue"
              closeIcon={<CloseOutlined aria-label={`Bỏ chọn ${s.name}`} />}
            >
              {s.name}
            </Tag>
          ))}
        </div>
      )}

      {grouped.map(([groupName, items]) => (
        <div key={groupName} style={{ marginBottom: 12 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12, fontWeight: 500 }}>
            {groupName}
          </Typography.Text>
          <div style={{ marginTop: 4 }}>
            {items.map((source) => (
              <div key={source.source_id} style={{ padding: "2px 0" }}>
                <Checkbox
                  checked={selectedIds.includes(source.source_id)}
                  onChange={() => onToggle(source.source_id)}
                >
                  {source.name}
                </Checkbox>
              </div>
            ))}
          </div>
        </div>
      ))}

      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {selectedIds.length}/{sources.length} đã chọn
      </Typography.Text>
    </div>
  );
}
