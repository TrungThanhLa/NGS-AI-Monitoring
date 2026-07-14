"use client";

import { Card, Col, Row, Typography } from "antd";
import Link from "next/link";

const items = [
  { href: "/system/master-data", title: "Dữ liệu dùng chung", desc: "Quản lý nhóm nguồn, nền tảng, chủ đề, từ khóa dùng chung" },
  { href: "/system/users", title: "Người dùng & phân quyền", desc: "Quản lý tài khoản, nhóm quyền" },
  { href: "/system/audit-logs", title: "Nhật ký hệ thống", desc: "Lịch sử thao tác trên hệ thống" },
  { href: "/system/alert-rules", title: "Cấu hình cảnh báo", desc: "Thiết lập ngưỡng và quy tắc sinh cảnh báo" },
  { href: "/system/crawler-settings", title: "Cấu hình Crawler", desc: "Thiết lập tham số thu thập dữ liệu" },
  { href: "/system/report-settings", title: "Cấu hình báo cáo", desc: "Thiết lập mẫu và hiển thị báo cáo" },
  { href: "/system/settings", title: "Tham số hệ thống", desc: "Cấu hình bảo mật, phiên đăng nhập" },
];

export default function SystemPage() {
  return (
    <div>
      <Typography.Title level={3}>Cấu hình hệ thống</Typography.Title>
      <Row gutter={[16, 16]}>
        {items.map((item) => (
          <Col span={8} key={item.href}>
            <Link href={item.href}>
              <Card hoverable title={item.title}>
                {item.desc}
              </Card>
            </Link>
          </Col>
        ))}
      </Row>
    </div>
  );
}
