import { useEffect, useRef, useState } from "react";
import { Alert, Avatar, Button, Card, Form, Input, message } from "antd";
import { UploadOutlined, UserOutlined } from "@ant-design/icons";
import PageHeader from "@/components/common/PageHeader";
import { useAuth } from "@/lib/AuthContext";
import { authFetch } from "@/lib/api";

type ChangePasswordFormValues = {
  current_password: string;
  new_password: string;
  confirm_password: string;
};

type ProfileFormValues = {
  full_name: string;
  email: string;
  phone: string;
};

const AVATAR_ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const AVATAR_MAX_SIZE = 2 * 1024 * 1024; // 2MB

export default function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const [passwordForm] = Form.useForm<ChangePasswordFormValues>();
  const [profileForm] = Form.useForm<ProfileFormValues>();
  const [submitting, setSubmitting] = useState(false);
  const [profileSubmitting, setProfileSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    profileForm.setFieldsValue({
      full_name: user?.full_name ?? "",
      email: user?.email ?? "",
      phone: user?.phone ?? "",
    });
  }, [user, profileForm]);

  useEffect(() => {
    if (!user?.avatar_url) {
      setAvatarPreview(null);
      return;
    }
    let objectUrl: string | null = null;
    authFetch(user.avatar_url)
      .then((res) => (res.ok ? res.blob() : null))
      .then((blob) => {
        if (!blob) return;
        objectUrl = URL.createObjectURL(blob);
        setAvatarPreview(objectUrl);
      })
      .catch(() => {});
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [user?.avatar_url]);

  async function onFinishProfile(values: ProfileFormValues) {
    setProfileSubmitting(true);
    setProfileError(null);
    try {
      const res = await authFetch("/api/auth/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: values.full_name,
          email: values.email,
          phone: values.phone || null,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: "Cập nhật thất bại" }));
        throw new Error(body.detail ?? "Cập nhật thất bại");
      }
      message.success("Cập nhật thông tin thành công");
      await refreshUser();
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Cập nhật thất bại");
    } finally {
      setProfileSubmitting(false);
    }
  }

  async function handleAvatarFile(file: File) {
    if (!AVATAR_ALLOWED_TYPES.includes(file.type)) {
      message.error("Chỉ chấp nhận ảnh JPG, PNG hoặc WEBP");
      return;
    }
    if (file.size > AVATAR_MAX_SIZE) {
      message.error("Ảnh không được vượt quá 2MB");
      return;
    }

    setAvatarUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await authFetch("/api/auth/me/avatar", { method: "POST", body: formData });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: "Tải ảnh thất bại" }));
        message.error(body.detail ?? "Tải ảnh thất bại");
        return;
      }
      setAvatarPreview(URL.createObjectURL(file));
      message.success("Cập nhật ảnh đại diện thành công");
      await refreshUser();
    } catch {
      message.error("Tải ảnh thất bại — lỗi kết nối");
    } finally {
      setAvatarUploading(false);
    }
  }

  function handleAvatarInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleAvatarFile(file);
    e.target.value = "";
  }

  async function onFinishPassword(values: ChangePasswordFormValues) {
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
      passwordForm.resetFields();
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
          {profileError && <Alert type="error" message={profileError} style={{ marginBottom: 16 }} showIcon />}

          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 20 }}>
            <input
              ref={inputRef}
              type="file"
              accept=".jpg,.jpeg,.png,.webp"
              style={{ display: "none" }}
              onChange={handleAvatarInputChange}
            />
            {avatarPreview ? (
              <img src={avatarPreview} alt="avatar" style={{ width: 64, height: 64, borderRadius: 8, objectFit: "cover" }} />
            ) : (
              <Avatar size={64} style={{ background: "#00859A", borderRadius: 8 }} icon={<UserOutlined />} />
            )}
            <div>
              <Button size="small" icon={<UploadOutlined />} loading={avatarUploading} onClick={() => inputRef.current?.click()}>
                {avatarPreview ? "Thay ảnh" : "Chọn ảnh"}
              </Button>
              <div style={{ fontSize: 12, color: "#8c8c8c", marginTop: 6 }}>JPG, PNG, WEBP — tối đa 2MB</div>
            </div>
          </div>

          <Form form={profileForm} layout="vertical" onFinish={onFinishProfile} requiredMark={false}>
            <Form.Item label="Tên đăng nhập">
              <Input value={user?.username} disabled />
            </Form.Item>
            <Form.Item name="full_name" label="Họ và tên" rules={[{ required: true, message: "Bắt buộc nhập họ tên" }]}>
              <Input placeholder="Nhập họ và tên" />
            </Form.Item>
            <Form.Item name="email" label="Email" rules={[{ required: true }, { type: "email", message: "Email không hợp lệ" }]}>
              <Input placeholder="Nhập email" />
            </Form.Item>
            <Form.Item
              name="phone"
              label="Số điện thoại"
              rules={[{ pattern: /^[0-9+\s-]{8,15}$/, message: "Số điện thoại không hợp lệ" }]}
            >
              <Input placeholder="Nhập số điện thoại (không bắt buộc)" />
            </Form.Item>
            <Form.Item style={{ marginBottom: 0 }}>
              <Button
                type="primary"
                htmlType="submit"
                loading={profileSubmitting}
                style={{ background: "#00859A", borderColor: "#00859A" }}
              >
                Lưu thay đổi
              </Button>
            </Form.Item>
          </Form>
        </Card>

        <Card title="Đổi mật khẩu" style={{ flex: "1 1 420px" }}>
          {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} showIcon />}
          <Form form={passwordForm} layout="vertical" onFinish={onFinishPassword} requiredMark={false}>
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
