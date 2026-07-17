import { useState } from "react";
import { Alert, Button, Card, Descriptions, Form, Input, message } from "antd";
import PageHeader from "@/components/common/PageHeader";
import { useAuth } from "@/lib/AuthContext";
import { authFetch } from "@/lib/api";

type ChangePasswordFormValues = {
  current_password: string;
  new_password: string;
  confirm_password: string;
};

export default function ProfilePage() {
  const { user } = useAuth();
  const [form] = Form.useForm<ChangePasswordFormValues>();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onFinish(values: ChangePasswordFormValues) {
    setSubmitting(true);
    setError(null);
    try {
      const res = await authFetch("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: values.current_password,
          new_password: values.new_password,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: "Đổi mật khẩu thất bại" }));
        throw new Error(body.detail ?? "Đổi mật khẩu thất bại");
      }
      message.success("Đổi mật khẩu thành công");
      form.resetFields();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đổi mật khẩu thất bại");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Thông tin cá nhân"
        breadcrumbs={[{ title: "Tổng quan", href: "/" }, { title: "Thông tin cá nhân" }]}
      />

      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
        <Card title="Thông tin tài khoản" style={{ flex: "1 1 420px" }}>
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="Tên đăng nhập">{user?.username}</Descriptions.Item>
            <Descriptions.Item label="Họ và tên">{user?.full_name || "-"}</Descriptions.Item>
            <Descriptions.Item label="Email">{user?.email || "-"}</Descriptions.Item>
          </Descriptions>
        </Card>

        <Card title="Đổi mật khẩu" style={{ flex: "1 1 420px" }}>
          {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} showIcon />}
          <Form form={form} layout="vertical" onFinish={onFinish} requiredMark={false}>
            <Form.Item
              name="current_password"
              label="Mật khẩu hiện tại"
              rules={[{ required: true, message: "Vui lòng nhập mật khẩu hiện tại" }]}
            >
              <Input.Password />
            </Form.Item>

            <Form.Item
              name="new_password"
              label="Mật khẩu mới"
              rules={[
                { required: true, message: "Vui lòng nhập mật khẩu mới" },
                {
                  pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/,
                  message: "Mật khẩu mới phải có tối thiểu 8 ký tự, gồm chữ hoa, chữ thường và số",
                },
              ]}
            >
              <Input.Password />
            </Form.Item>

            <Form.Item
              name="confirm_password"
              label="Xác nhận mật khẩu"
              dependencies={["new_password"]}
              rules={[
                { required: true, message: "Vui lòng xác nhận mật khẩu mới" },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (!value || getFieldValue("new_password") === value) return Promise.resolve();
                    return Promise.reject(new Error("Mật khẩu xác nhận không khớp"));
                  },
                }),
              ]}
            >
              <Input.Password />
            </Form.Item>

            <Form.Item style={{ marginBottom: 0 }}>
              <Button type="primary" htmlType="submit" loading={submitting} style={{ background: "#00859A", borderColor: "#00859A" }}>
                Đổi mật khẩu
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </div>
    </>
  );
}
