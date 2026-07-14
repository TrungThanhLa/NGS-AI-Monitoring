"use client";

import { Card, Form, InputNumber, Switch, Typography, Row, Col } from "antd";

export default function CrawlerSettingsPage() {
  return (
    <div>
      <Typography.Title level={3}>Cấu hình Crawler</Typography.Title>
      <Typography.Paragraph type="secondary">
        Các tham số dưới đây hiện đang là biến môi trường (`CRAWLER_DELAY_SECONDS`, `CRAWLER_MAX_RETRIES`,
        `CRAWLER_TIMEOUT_SECONDS`) — form này chỉ minh hoạ giao diện, chưa lưu được thật.
      </Typography.Paragraph>
      <Card>
        <Form layout="vertical">
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="Delay giữa các request (giây)">
                <InputNumber style={{ width: "100%" }} defaultValue={1.5} min={0} step={0.5} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="Số lần thử lại khi lỗi (retry_count)">
                <InputNumber style={{ width: "100%" }} defaultValue={3} min={0} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="Thời gian chờ mỗi request (giây)">
                <InputNumber style={{ width: "100%" }} defaultValue={30} min={1} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="Tuân thủ robots.txt" valuePropName="checked">
            <Switch defaultChecked />
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
