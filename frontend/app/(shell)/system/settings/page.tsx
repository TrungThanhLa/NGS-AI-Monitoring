"use client";

import { Card, Form, InputNumber, Typography } from "antd";

export default function SystemSettingsPage() {
  return (
    <div>
      <Typography.Title level={3}>Tham số hệ thống</Typography.Title>
      <Card>
        <Form layout="vertical">
          <Form.Item label="Số lần đăng nhập sai tối đa">
            <InputNumber style={{ width: "100%" }} defaultValue={5} min={1} />
          </Form.Item>
          <Form.Item label="Thời gian hết phiên (phút)">
            <InputNumber style={{ width: "100%" }} defaultValue={60} min={1} />
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
