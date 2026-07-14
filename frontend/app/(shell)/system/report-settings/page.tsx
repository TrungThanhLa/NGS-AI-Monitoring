"use client";

import { Card, Form, Input, Typography } from "antd";

export default function ReportSettingsPage() {
  return (
    <div>
      <Typography.Title level={3}>Cấu hình báo cáo</Typography.Title>
      <Typography.Paragraph type="secondary">
        Mẫu báo cáo DOCX hiện tại là file tĩnh (`templates/report_template.docx`) — form này chỉ minh hoạ
        giao diện, chưa lưu được thật.
      </Typography.Paragraph>
      <Card>
        <Form layout="vertical">
          <Form.Item label="Tên tổ chức">
            <Input defaultValue="Cục An ninh mạng và phòng, chống tội phạm sử dụng công nghệ cao" />
          </Form.Item>
          <Form.Item label="Đơn vị báo cáo">
            <Input defaultValue="Phòng Giám sát không gian mạng" />
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
