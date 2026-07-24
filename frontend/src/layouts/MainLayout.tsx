import { useEffect, useState } from "react";
import { Layout, Menu, Avatar, Badge, Typography, Space, Button, Dropdown } from "antd";
import type { MenuProps } from "antd";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import Logo from "@/components/common/Logo";
import { useAuth } from "@/lib/AuthContext";
import { authFetch } from "@/lib/api";
import {
  DashboardOutlined,
  RadarChartOutlined,
  GlobalOutlined,
  FileTextOutlined,
  WarningOutlined,
  SafetyCertificateOutlined,
  BarChartOutlined,
  SettingOutlined,
  UserOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  BellOutlined,
  LogoutOutlined,
} from "@ant-design/icons";

const { Sider, Header, Content } = Layout;

const MENU_ITEMS = [
  { key: "/", icon: <DashboardOutlined />, label: "Tổng quan" },
  { key: "/campaigns", icon: <RadarChartOutlined />, label: "Chiến dịch giám sát" },
  { key: "/sources", icon: <GlobalOutlined />, label: "Nguồn dữ liệu" },
  { key: "/contents", icon: <FileTextOutlined />, label: "Nội dung" },
  { key: "/alerts", icon: <WarningOutlined />, label: "Cảnh báo" },
  { key: "/cases", icon: <SafetyCertificateOutlined />, label: "Vụ việc" },
  { key: "/reports", icon: <BarChartOutlined />, label: "Báo cáo" },
  {
    key: "/system",
    icon: <SettingOutlined />,
    label: "Cấu hình hệ thống",
    children: [
      {
        key: "/system/users-group",
        label: "Người dùng & phân quyền",
        children: [
          { key: "/system/users", label: "Danh sách người dùng" },
          { key: "/system/roles", label: "Nhóm quyền" },
        ],
      },
      { key: "/system/master-data", label: "Dữ liệu danh mục" },
      { key: "/system/settings", label: "Cài đặt hệ thống" },
      { key: "/system/connectors", label: "Cấu hình Connector" },
      { key: "/system/audit-logs", label: "Nhật ký hoạt động" },
    ],
  },
];

const SYSTEM_SUBMENU_PERMISSION: Record<string, string> = {
  "/system/users": "user.manage",
  "/system/roles": "role.manage",
  "/system/audit-logs": "audit_log.view",
  "/system/master-data": "system.configure",
  "/system/settings": "system.configure",
  "/system/connectors": "system.configure",
};

function filterMenuByPermission(items: typeof MENU_ITEMS, permissions: string[]): typeof MENU_ITEMS {
  return items
    .map((item) => {
      if (item.children) {
        const children = filterMenuByPermission(item.children as typeof MENU_ITEMS, permissions);
        if (children.length === 0) return null;
        return { ...item, children };
      }
      const required = SYSTEM_SUBMENU_PERMISSION[item.key];
      if (required && !permissions.includes(required)) return null;
      return item;
    })
    .filter((item): item is NonNullable<typeof item> => item !== null);
}

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const visibleMenuItems = filterMenuByPermission(MENU_ITEMS, user?.permissions ?? []);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);

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
    // Phụ thuộc cả `user` (không chỉ avatar_url) — avatar_url là URL endpoint cố định
    // (VD "/api/auth/me/avatar"), không đổi giữa các lần upload lại ảnh, nên nếu chỉ phụ
    // thuộc avatar_url thì sau khi refreshUser() (đổi ảnh mới) effect sẽ không chạy lại
  }, [user]);

  const selectedKey = (() => {
    const path = location.pathname;
    if (path === "/") return ["/"];
    const match = MENU_ITEMS.flatMap((m) =>
      m.children ? m.children.flatMap((c) => (c.children ? c.children.map((cc) => cc.key) : [c.key])) : [m.key]
    ).find((k) => k !== "/" && path.startsWith(k));
    return match ? [match] : [path];
  })();

  const openKeys = (() => {
    const keys: string[] = [];
    for (const m of MENU_ITEMS) {
      if (!m.children) continue;
      for (const c of m.children) {
        const childMatches = c.children
          ? c.children.some((cc) => location.pathname.startsWith(cc.key))
          : location.pathname.startsWith(c.key);
        if (childMatches) {
          keys.push(m.key);
          if (c.children) keys.push(c.key);
        }
      }
    }
    return keys;
  })();

  const userMenuItems: MenuProps["items"] = [
    { key: "profile", icon: <UserOutlined />, label: "Thông tin cá nhân" },
    { type: "divider" },
    { key: "logout", icon: <LogoutOutlined />, label: "Đăng xuất", danger: true },
  ];

  function handleUserMenuClick({ key }: { key: string }) {
    if (key === "logout") {
      logout();
      navigate("/login");
      return;
    }
    navigate("/profile");
  }

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        collapsible
        collapsed={collapsed}
        collapsedWidth={80}
        trigger={null}
        width={240}
        style={{ background: "#0A1D55", position: "fixed", height: "100vh", left: 0, top: 0, zIndex: 100, display: "flex", flexDirection: "column" }}
      >
        <div
          onClick={() => navigate("/")}
          style={{
            height: 72,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: collapsed ? 8 : "0 18px",
            borderBottom: "1px solid rgba(255,255,255,0.1)",
            background: "rgba(0,0,0,0.15)",
            flexShrink: 0,
            cursor: "pointer",
          }}
        >
          <Logo collapsed={collapsed} />
        </div>

        <div style={{ overflowY: "auto", overflowX: "hidden", flex: 1, height: "calc(100vh - 72px)" }} className="ngs-sidebar-scroll">
          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={selectedKey}
            defaultOpenKeys={openKeys}
            items={visibleMenuItems}
            onClick={({ key }) => navigate(key)}
            style={{ background: "#0A1D55", border: "none", marginTop: 8 }}
          />
        </div>
      </Sider>

      <Layout style={{ marginLeft: collapsed ? 80 : 240, transition: "margin-left 0.2s" }}>
        <Header
          style={{
            background: "#FFFFFF",
            padding: "0 24px",
            height: 64,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            boxShadow: "0 1px 4px rgba(0,21,41,0.08)",
            position: "sticky",
            top: 0,
            zIndex: 99,
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ fontSize: 16, color: "#0A1D55" }}
          />

          <Space size={16}>
            <Badge count={5} size="small">
              <Button type="text" icon={<BellOutlined style={{ fontSize: 18 }} />} />
            </Badge>
            <Dropdown
              menu={{ items: userMenuItems, onClick: handleUserMenuClick }}
              placement="bottomRight"
              trigger={["click"]}
            >
              <Space style={{ cursor: "pointer" }}>
                <Avatar style={{ background: "#00859A" }} size={32} src={avatarPreview ?? undefined} icon={<UserOutlined />} />
                {!collapsed && (
                  <Typography.Text strong style={{ color: "#0A1D55" }}>
                    {user?.full_name || user?.username}
                  </Typography.Text>
                )}
              </Space>
            </Dropdown>
          </Space>
        </Header>

        <Content style={{ padding: 24, background: "#F5F7FA", minHeight: "calc(100vh - 64px)" }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
