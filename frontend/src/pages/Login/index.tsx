import { useState } from "react";
import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onFinish(values: { username: string; password: string }) {
    setSubmitting(true);
    setError(null);
    try {
      await login(values.username, values.password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card
      style={{ borderRadius: 16, boxShadow: "0 8px 40px rgba(10,29,85,0.25)", width: 420 }}
      styles={{ body: { padding: "40px 36px 36px" } }}
    >
      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <img src="/logo.svg" alt="NGS" style={{ height: 56, width: "auto" }} />
      </div>

      <Typography.Title level={4} style={{ textAlign: "center", margin: "0 0 6px", color: "#0A1D55" }}>
        Đăng nhập hệ thống
      </Typography.Title>
      <Typography.Text type="secondary" style={{ display: "block", textAlign: "center", marginBottom: 28, fontSize: 13 }}>
        Vui lòng nhập tài khoản để tiếp tục
      </Typography.Text>

      {error && <Alert type="error" message={error} style={{ marginBottom: 20, borderRadius: 8 }} showIcon />}

      <Form layout="vertical" onFinish={onFinish} requiredMark={false}>
        <Form.Item name="username" label="Tên đăng nhập" rules={[{ required: true, message: "Vui lòng nhập tên đăng nhập" }]}>
          <Input prefix={<UserOutlined />} placeholder="Tên đăng nhập" size="large" autoFocus />
        </Form.Item>

        <Form.Item name="password" label="Mật khẩu" rules={[{ required: true, message: "Vui lòng nhập mật khẩu" }]}>
          <Input.Password prefix={<LockOutlined />} placeholder="Mật khẩu" size="large" />
        </Form.Item>

        <Form.Item style={{ marginBottom: 0, marginTop: 8 }}>
          <Button
            type="primary"
            htmlType="submit"
            block
            size="large"
            loading={submitting}
            style={{ background: "#00859A", borderColor: "#00859A", borderRadius: 8, height: 48, fontSize: 15 }}
          >
            Đăng nhập
          </Button>
        </Form.Item>
      </Form>

      <Typography.Text type="secondary" style={{ display: "block", textAlign: "center", marginTop: 24, fontSize: 12 }}>
        NGS Monitor Platform © 2026 — DCV Group
      </Typography.Text>
    </Card>
  );
}
