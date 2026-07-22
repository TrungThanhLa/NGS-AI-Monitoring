import { useEffect, useState } from "react";
import { Button, Card, DatePicker, Space, Tag, Alert, Select, Typography } from "antd";
import dayjs, { Dayjs } from "dayjs";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import PermissionGuard from "@/components/common/PermissionGuard";
import { authFetch } from "@/lib/api";
import { useAuth } from "@/lib/AuthContext";
import SourceSidebar, { SourceItem } from "./SourceSidebar";
import SummaryCard from "./SummaryCard";

const CAMPAIGN_ID_STORAGE_KEY = "ngs_monitor_one_shot_campaign_id";

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

type CampaignStatus = {
  campaign_id: string;
  status: string;
};

type KeywordOption = { keyword_id: string; keyword: string };

const statusColor: Record<string, string> = {
  DRAFT: "default",
  ACTIVE: "blue",
  COMPLETED: "green",
  ARCHIVED: "default",
};

export default function ReportCreate() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [dateFrom, setDateFrom] = useState<Dayjs>(todayMinus(7));
  const [dateTo, setDateTo] = useState<Dayjs>(todayMinus(0));
  const [campaign, setCampaign] = useState<CampaignStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [keywords, setKeywords] = useState<KeywordOption[]>([]);
  const [selectedKeywordIds, setSelectedKeywordIds] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    authFetch("/api/sources").then((res) => (res.ok ? res.json() : { sources: [] })).then((data) => setSources(data.sources ?? []));
    authFetch("/api/keywords").then((res) => (res.ok ? res.json() : { keywords: [] })).then((data) => setKeywords(data.keywords ?? []));
  }, []);

  function toggleSource(sourceId: string) {
    setSelectedSourceIds((prev) => (prev.includes(sourceId) ? prev.filter((id) => id !== sourceId) : [...prev, sourceId]));
  }

  function applyPreset(days: number) {
    setDateFrom(todayMinus(days));
    setDateTo(todayMinus(0));
  }

  const parsedDayCount = dateTo.diff(dateFrom, "day");
  const dayCount = Number.isFinite(parsedDayCount) ? Math.max(1, parsedDayCount) : 1;

  // Cập nhật status Campaign + tự dọn sessionStorage khi Campaign đã ở trạng thái
  // không còn ACTIVE (COMPLETED — ONE_SHOT tự chuyển sau khi chord crawl xong)
  function updateCampaignStatus(data: CampaignStatus) {
    setCampaign(data);
    if (data.status !== "ACTIVE") {
      sessionStorage.removeItem(CAMPAIGN_ID_STORAGE_KEY);
    }
  }

  // Khôi phục Campaign đang ACTIVE sau F5 — giữ đúng pattern job cũ
  useEffect(() => {
    const savedId = sessionStorage.getItem(CAMPAIGN_ID_STORAGE_KEY);
    if (!savedId) return;
    authFetch(`/api/campaigns/${savedId}`).then((res) => {
      if (!res.ok) {
        sessionStorage.removeItem(CAMPAIGN_ID_STORAGE_KEY);
        return;
      }
      res.json().then(updateCampaignStatus);
    });
  }, []);

  // Polling mỗi 3 giây trong lúc Campaign đang ACTIVE (chord Celery đang crawl toàn bộ
  // nguồn đã chọn) — dừng khi status đổi sang COMPLETED. Cờ `cancelled` chặn race
  // condition nếu response về sau khi effect đã cleanup (giống pattern job cũ).
  useEffect(() => {
    if (!campaign || campaign.status !== "ACTIVE") return;
    let cancelled = false;
    const interval = setInterval(async () => {
      const res = await authFetch(`/api/campaigns/${campaign.campaign_id}`);
      if (cancelled || !res.ok) return;
      updateCampaignStatus(await res.json());
    }, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [campaign?.campaign_id, campaign?.status]);

  // Tạo Campaign mode=ONE_SHOT rồi activate ngay — thay thế POST /api/reports/create cũ
  // (Phase 7). Activate dispatch 1 Celery chord crawl toàn bộ nguồn đã chọn, tự chuyển
  // status sang COMPLETED khi xong (backend/routers/campaigns.py + workers/campaign_tasks.py).
  // Chặn double-click bằng `submitting`, lưu campaign_id vào sessionStorage để effect
  // khôi phục sau F5 tìm lại được (giữ đúng pattern job cũ).
  async function handleSubmit() {
    if (!user) return;
    setSubmitting(true);
    setError(null);
    try {
      const createRes = await authFetch("/api/campaigns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: `Báo cáo nhanh ${dayjs().format("DD/MM/YYYY HH:mm")}`,
          mode: "ONE_SHOT",
          owner_id: user.user_id,
          start_date: dateFrom.format("YYYY-MM-DD"),
          end_date: dateTo.format("YYYY-MM-DD"),
          source_ids: selectedSourceIds,
          keyword_ids: selectedKeywordIds,
        }),
      });
      if (!createRes.ok) {
        const body = await createRes.json().catch(() => ({}));
        setError(body.detail || "Tạo chiến dịch thất bại");
        return;
      }
      const created = await createRes.json();

      const activateRes = await authFetch(`/api/campaigns/${created.campaign_id}/activate`, { method: "POST" });
      if (!activateRes.ok) {
        const body = await activateRes.json().catch(() => ({}));
        setError(body.detail || "Kích hoạt thất bại");
        return;
      }
      const activated = await activateRes.json();
      sessionStorage.setItem(CAMPAIGN_ID_STORAGE_KEY, activated.campaign_id);
      updateCampaignStatus(activated);
    } finally {
      setSubmitting(false);
    }
  }

  const campaignActive = campaign?.status === "ACTIVE";
  const disabled =
    !dateFrom ||
    !dateTo ||
    dateFrom.isAfter(dateTo) ||
    selectedSourceIds.length === 0 ||
    selectedKeywordIds.length === 0 ||
    !user ||
    campaignActive ||
    submitting;

  return (
    <div>
      <PageHeader
        title="Tạo báo cáo nhanh"
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
              <Typography.Text>Từ khóa (bắt buộc ≥1)</Typography.Text>
              <Select
                mode="multiple"
                style={{ width: "100%", marginBottom: 12 }}
                placeholder="Chọn từ khóa cần theo dõi"
                value={selectedKeywordIds}
                onChange={setSelectedKeywordIds}
                options={keywords.map((k) => ({ value: k.keyword_id, label: k.keyword }))}
              />
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

          {campaign && (
            <div>
              <Space align="center">
                <Tag color={statusColor[campaign.status]}>{campaign.status}</Tag>
                <Typography.Text>
                  {campaign.status === "ACTIVE" && "Đang crawl toàn bộ nguồn đã chọn..."}
                  {campaign.status === "COMPLETED" && "Crawl xong — vào trang chiến dịch để tạo báo cáo."}
                </Typography.Text>
              </Space>
              {campaign.status === "COMPLETED" && (
                <div style={{ marginTop: 8 }}>
                  <Button type="link" onClick={() => navigate(`/campaigns/${campaign.campaign_id}`)}>
                    Đến trang chiến dịch để tạo báo cáo →
                  </Button>
                </div>
              )}
            </div>
          )}
        </Space>
      </Card>
    </div>
  );
}
