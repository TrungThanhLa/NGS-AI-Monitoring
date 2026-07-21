import { useEffect, useState } from "react";
import { App, Button, Card, Col, Descriptions, Input, Row, Select, Space, Tag, Typography } from "antd";
import { ArrowLeftOutlined, LinkOutlined } from "@ant-design/icons";
import { useNavigate, useParams } from "react-router-dom";
import StatusTag from "@/components/common/StatusTag";
import PageHeader from "@/components/common/PageHeader";
import LoadingState from "@/components/common/LoadingState";
import PermissionGuard from "@/components/common/PermissionGuard";
import { authFetch } from "@/lib/api";
import dayjs from "dayjs";

const REVIEW_OPTIONS = [
  { value: "REVIEWED", label: "Đã xem xét" },
  { value: "NEED_VERIFY", label: "Cần xác minh" },
  { value: "VERIFIED", label: "Đã xác minh" },
  { value: "NOT_RELEVANT", label: "Không liên quan" },
  { value: "CASE_CREATED", label: "Tạo vụ việc" },
];

type ContentAnalysis = {
  analysis_id: string;
  topics: string[];
  keywords: string[];
  sentiment: string | null;
  emotion: string | null;
  confidence: number | null;
  needs_review: boolean;
  summary: string | null;
  ai_model: string;
  analyzed_at: string;
};

type ContentDetailData = {
  article_id: string;
  url: string;
  title: string | null;
  published_at: string | null;
  review_status: string;
  source_name: string | null;
  content_raw: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  reviewer_note: string | null;
  campaigns: { campaign_id: string; name: string }[];
  analysis: ContentAnalysis | null;
};

export default function ContentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();

  const [data, setData] = useState<ContentDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    authFetch(`/api/contents/${id}`)
      .then((res) => {
        if (res.status === 404) {
          setNotFound(true);
          return null;
        }
        return res.ok ? res.json() : null;
      })
      .then((body: ContentDetailData | null) => {
        if (body) {
          setData(body);
          setNote(body.reviewer_note ?? "");
        }
      })
      .catch(() => message.error("Không tải được nội dung"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleReview = (reviewStatus: string) => {
    if (!id) return;
    setSubmitting(true);
    authFetch(`/api/contents/${id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review_status: reviewStatus, note: note || null }),
    })
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then((body: ContentDetailData) => {
        setData(body);
        message.success("Đã cập nhật trạng thái đánh giá");
      })
      .catch(() => message.error("Cập nhật thất bại"))
      .finally(() => setSubmitting(false));
  };

  if (loading) return <LoadingState />;
  if (notFound || !data) return <Typography.Text type="secondary">Không tìm thấy nội dung</Typography.Text>;

  return (
    <div>
      <PageHeader
        title={data.title ?? data.url}
        breadcrumbs={[
          { title: "Tổng quan", href: "/" },
          { title: "Nội dung", href: "/contents" },
          { title: "Chi tiết" },
        ]}
        extra={
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/contents")}>
              Quay lại
            </Button>
            <PermissionGuard permission="content.review">
              <Select
                placeholder="Cập nhật trạng thái"
                style={{ width: 180 }}
                onChange={handleReview}
                options={REVIEW_OPTIONS}
                disabled={submitting}
              />
            </PermissionGuard>
          </Space>
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="Nội dung" style={{ borderRadius: 12 }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="URL">
                <a href={data.url} target="_blank" rel="noopener noreferrer">
                  <LinkOutlined /> {data.url}
                </a>
              </Descriptions.Item>
              <Descriptions.Item label="Nguồn">{data.source_name ?? "—"}</Descriptions.Item>
              <Descriptions.Item label="Chiến dịch">
                {data.campaigns.length > 0 ? data.campaigns.map((c) => c.name).join(", ") : "—"}
              </Descriptions.Item>
              <Descriptions.Item label="Ngày đăng">
                {data.published_at ? dayjs(data.published_at).format("DD/MM/YYYY HH:mm") : "—"}
              </Descriptions.Item>
            </Descriptions>

            {data.analysis?.summary && (
              <div style={{ marginTop: 16 }}>
                <Typography.Text strong>Tóm tắt:</Typography.Text>
                <Typography.Paragraph style={{ marginTop: 8 }}>{data.analysis.summary}</Typography.Paragraph>
              </div>
            )}

            {data.content_raw && (
              <div style={{ marginTop: 16 }}>
                <Typography.Text strong>Nội dung đầy đủ:</Typography.Text>
                <Typography.Paragraph
                  style={{ marginTop: 8, whiteSpace: "pre-wrap", maxHeight: 400, overflow: "auto" }}
                >
                  {data.content_raw}
                </Typography.Paragraph>
              </div>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="Phân tích AI" style={{ borderRadius: 12, marginBottom: 16 }}>
            {data.analysis ? (
              <Space direction="vertical" style={{ width: "100%" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>Cảm xúc:</span>
                  {data.analysis.sentiment ? (
                    <StatusTag type="sentiment" value={data.analysis.sentiment.toUpperCase()} />
                  ) : (
                    <span>—</span>
                  )}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>Độ tin cậy:</span>
                  <Tag color="blue">
                    {data.analysis.confidence != null ? `${Math.round(data.analysis.confidence * 100)}%` : "—"}
                  </Tag>
                </div>
                {data.analysis.needs_review && <Tag color="warning">Cần xem xét thêm</Tag>}

                {data.analysis.topics.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      Chủ đề:
                    </Typography.Text>
                    <div style={{ marginTop: 4 }}>
                      {data.analysis.topics.map((t) => (
                        <Tag key={t}>{t}</Tag>
                      ))}
                    </div>
                  </div>
                )}
                {data.analysis.keywords.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      Từ khóa:
                    </Typography.Text>
                    <div style={{ marginTop: 4 }}>
                      {data.analysis.keywords.map((k) => (
                        <Tag key={k} color="blue">
                          {k}
                        </Tag>
                      ))}
                    </div>
                  </div>
                )}
              </Space>
            ) : (
              <Typography.Text type="secondary">Chưa có kết quả phân tích AI</Typography.Text>
            )}
          </Card>

          <Card title="Trạng thái xem xét" style={{ borderRadius: 12 }}>
            <Space direction="vertical" style={{ width: "100%" }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span>Trạng thái:</span>
                <StatusTag type="content" value={data.review_status} />
              </div>
              {data.reviewed_at && (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  Đánh giá lúc {dayjs(data.reviewed_at).format("DD/MM/YYYY HH:mm")}
                </Typography.Text>
              )}
              <PermissionGuard permission="content.review">
                <Input.TextArea
                  placeholder="Ghi chú đánh giá (áp dụng khi bấm cập nhật trạng thái ở trên)..."
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={3}
                />
              </PermissionGuard>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
