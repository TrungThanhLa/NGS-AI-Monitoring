import { useEffect, useState } from "react";
import { Button, Card, DatePicker, Input, Select, Space, Table, Typography } from "antd";
import { SearchOutlined, EyeOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import StatusTag from "@/components/common/StatusTag";
import PageHeader from "@/components/common/PageHeader";
import { authFetch } from "@/lib/api";
import dayjs from "dayjs";

const { RangePicker } = DatePicker;

type ContentListItem = {
  article_id: string;
  url: string;
  title: string | null;
  author: string | null;
  published_at: string | null;
  crawled_at: string | null;
  status: string;
  review_status: string;
  source_id: string | null;
  source_name: string | null;
  campaign_ids: string[];
  sentiment: string | null;
  emotion: string | null;
  needs_review: boolean | null;
};

type CampaignOption = { campaign_id: string; name: string };

export default function ContentsPage() {
  const navigate = useNavigate();
  const [contents, setContents] = useState<ContentListItem[]>([]);
  const [campaigns, setCampaigns] = useState<CampaignOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [keyword, setKeyword] = useState("");
  const [reviewStatus, setReviewStatus] = useState("");
  const [sentiment, setSentiment] = useState("");
  const [campaignId, setCampaignId] = useState("");
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (reviewStatus) params.set("review_status", reviewStatus);
    if (sentiment) params.set("sentiment", sentiment);
    if (campaignId) params.set("campaign_id", campaignId);
    if (dateRange?.[0]) params.set("date_from", dateRange[0].format("YYYY-MM-DD"));
    if (dateRange?.[1]) params.set("date_to", dateRange[1].format("YYYY-MM-DD"));

    authFetch(`/api/contents?${params.toString()}`)
      .then((res) => (res.ok ? res.json() : { contents: [] }))
      .then((data) => {
        setContents(data.contents ?? []);
        setError(null);
      })
      .catch(() => setError("Không tải được danh sách nội dung"))
      .finally(() => setLoading(false));
  }, [reviewStatus, sentiment, campaignId, dateRange]);

  useEffect(() => {
    authFetch("/api/campaigns")
      .then((res) => (res.ok ? res.json() : { campaigns: [] }))
      .then((data) => setCampaigns(data.campaigns ?? []))
      .catch(() => setCampaigns([]));
  }, []);

  // "keyword" (tìm tiêu đề) không có trong contract API rule 05 — lọc client-side
  const filtered = contents.filter(
    (c) => !keyword || (c.title ?? "").toLowerCase().includes(keyword.toLowerCase()),
  );

  const columns = [
    {
      title: "Tiêu đề",
      dataIndex: "title",
      key: "title",
      render: (v: string | null, r: ContentListItem) => (
        <a onClick={() => navigate(`/contents/${r.article_id}`)} style={{ color: "#0B1F3A", fontWeight: 500 }}>
          {v ?? r.url}
        </a>
      ),
    },
    {
      title: "Nguồn",
      dataIndex: "source_name",
      key: "source_name",
      render: (v: string | null) => v ?? "—",
    },
    {
      title: "Cảm xúc",
      dataIndex: "sentiment",
      key: "sentiment",
      render: (v: string | null) => (v ? <StatusTag type="sentiment" value={v.toUpperCase()} /> : "—"),
    },
    {
      title: "Trạng thái",
      dataIndex: "review_status",
      key: "review_status",
      render: (v: string) => <StatusTag type="content" value={v} />,
    },
    {
      title: "Ngày đăng",
      dataIndex: "published_at",
      key: "published_at",
      render: (v: string | null) => (v ? dayjs(v).format("DD/MM/YYYY") : "—"),
    },
    {
      title: "",
      key: "action",
      width: 48,
      render: (_: unknown, r: ContentListItem) => (
        <Button type="text" icon={<EyeOutlined />} onClick={() => navigate(`/contents/${r.article_id}`)} />
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Nội dung"
        subtitle="Theo dõi và xem xét các nội dung thu thập được"
        breadcrumbs={[{ title: "Tổng quan", href: "/" }, { title: "Nội dung" }]}
      />

      {error && (
        <Typography.Text type="danger" style={{ display: "block", marginBottom: 16 }}>
          {error}
        </Typography.Text>
      )}

      <Card style={{ borderRadius: 12 }}>
        <Space wrap style={{ marginBottom: 16 }}>
          <Input
            placeholder="Tìm kiếm theo tiêu đề..."
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 240 }}
            allowClear
          />
          <Select
            value={campaignId}
            onChange={(v) => setCampaignId(v)}
            style={{ width: 200 }}
            options={[
              { value: "", label: "Tất cả chiến dịch" },
              ...campaigns.map((c) => ({ value: c.campaign_id, label: c.name })),
            ]}
          />
          <Select
            value={reviewStatus}
            onChange={(v) => setReviewStatus(v)}
            options={[
              { value: "", label: "Tất cả trạng thái" },
              { value: "NEW", label: "Mới" },
              { value: "REVIEWED", label: "Đã xem xét" },
              { value: "NEED_VERIFY", label: "Cần xác minh" },
              { value: "VERIFIED", label: "Đã xác minh" },
              { value: "NOT_RELEVANT", label: "Không liên quan" },
              { value: "CASE_CREATED", label: "Đã tạo vụ việc" },
            ]}
            style={{ width: 160 }}
          />
          <Select
            value={sentiment}
            onChange={(v) => setSentiment(v)}
            options={[
              { value: "", label: "Tất cả cảm xúc" },
              { value: "positive", label: "Tích cực" },
              { value: "negative", label: "Tiêu cực" },
              { value: "neutral", label: "Trung lập" },
            ]}
            style={{ width: 140 }}
          />
          <RangePicker
            format="DD/MM/YYYY"
            onChange={(v) => setDateRange(v as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null)}
          />
        </Space>

        <Table
          columns={columns}
          dataSource={filtered}
          rowKey="article_id"
          loading={loading}
          pagination={{
            pageSize: 20,
            showTotal: (t) => `Tổng ${t} nội dung`,
          }}
        />
      </Card>
    </div>
  );
}
