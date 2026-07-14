import { Card, Table, Tag, Typography } from "antd";
import PageHeader from "@/components/common/PageHeader";
import { connectors } from "@/data/mockData";

const STATUS_COLOR: Record<string, string> = {
  ACTIVE: "success",
  WARNING: "warning",
  PAUSED: "default",
};

export default function ConnectorsPage() {
  return (
    <div>
      <PageHeader
        title="Cấu hình Connector"
        subtitle="Trạng thái kết nối thu thập dữ liệu theo từng nền tảng"
        breadcrumbs={[{ title: "Tổng quan", href: "/" }, { title: "Cấu hình hệ thống" }, { title: "Cấu hình Connector" }]}
      />
      <Typography.Paragraph type="secondary">
        Trang này chỉ minh hoạ giao diện — chưa có chức năng chỉnh sửa cấu hình proxy/fallback thật.
      </Typography.Paragraph>
      <Card style={{ borderRadius: 12 }}>
        <Table
          rowKey="id"
          dataSource={connectors}
          pagination={false}
          columns={[
            { title: "Nền tảng", dataIndex: "platform" },
            { title: "Tên Connector", dataIndex: "name" },
            { title: "Phương thức", dataIndex: "method" },
            {
              title: "Trạng thái",
              dataIndex: "status",
              render: (v: string) => <Tag color={STATUS_COLOR[v] ?? "default"}>{v}</Tag>,
            },
            {
              title: "Tỷ lệ thành công",
              dataIndex: "success_rate",
              render: (v: number | null) => (v == null ? "—" : `${v}%`),
            },
            { title: "Kiểm tra lần cuối", dataIndex: "last_checked_at", render: (v: string) => new Date(v).toLocaleString("vi-VN") },
          ]}
        />
      </Card>
    </div>
  );
}
