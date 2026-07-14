"use client";

import { useState } from "react";
import { Layout, Menu, Badge, Avatar, Typography, Space, Dropdown } from "antd";
import {
  BellOutlined,
  MessageOutlined,
  UserOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  DoubleLeftOutlined,
  DoubleRightOutlined,
  DownOutlined,
  LogoutOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { usePathname, useRouter } from "next/navigation";
import { sidebarItems, pageTitles } from "./menuConfig";

const { Sider, Header, Content, Footer } = Layout;
const { Text } = Typography;

function Logo({ collapsed }: { collapsed: boolean }) {
  const letters: { text: string; bg: string }[] = [
    { text: "N", bg: "#2E6FF2" },
    { text: "G", bg: "#7C6EF0" },
    { text: "S", bg: "#10B981" },
  ];
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "16px 20px",
        borderBottom: "1px solid rgba(255,255,255,0.08)",
        overflow: "hidden",
      }}
    >
      <div style={{ display: "flex", gap: 2, flexShrink: 0 }}>
        {letters.map((l) => (
          <div
            key={l.text}
            style={{
              width: 22,
              height: 22,
              background: l.bg,
              color: "#fff",
              fontWeight: 800,
              fontSize: 12,
              borderRadius: 5,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {l.text}
          </div>
        ))}
      </div>
      {!collapsed && (
        <div style={{ minWidth: 0 }}>
          <div style={{ color: "#fff", fontWeight: 700, fontSize: 17, lineHeight: 1.1 }}>NGS</div>
          <div
            style={{
              fontSize: 10.5,
              fontWeight: 400,
              color: "rgba(255,255,255,0.55)",
              whiteSpace: "nowrap",
            }}
          >
            Minh bạch hóa mọi thông tin
          </div>
        </div>
      )}
    </div>
  );
}

function SidebarProfile({ collapsed }: { collapsed: boolean }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "12px 20px",
        borderTop: "1px solid rgba(255,255,255,0.08)",
        color: "#fff",
      }}
    >
      <Avatar size={32} icon={<UserOutlined />} style={{ background: "#2E6FF2", flexShrink: 0 }} />
      {!collapsed && (
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.3 }}>Nguyễn Văn A</div>
          <div style={{ fontSize: 11.5, color: "rgba(255,255,255,0.55)" }}>Quản trị hệ thống</div>
        </div>
      )}
    </div>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);

  const openKey = "/" + pathname.split("/")[1];
  const selectedKey = pathname.startsWith("/system") ? pathname : openKey;

  const isSystemSub = pathname.startsWith("/system/");
  const currentTitle = pageTitles[pathname] ?? pageTitles[openKey] ?? "";
  const parentTitle = isSystemSub ? pageTitles["/system"] : null;

  const userMenuItems = [
    { key: "profile", icon: <UserOutlined />, label: "Hồ sơ cá nhân" },
    { key: "settings", icon: <SettingOutlined />, label: "Cài đặt tài khoản" },
    { type: "divider" as const },
    { key: "logout", icon: <LogoutOutlined />, label: "Đăng xuất", danger: true },
  ];

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        width={240}
        collapsedWidth={72}
        collapsed={collapsed}
        trigger={null}
        theme="dark"
        style={{ display: "flex", flexDirection: "column" }}
      >
        <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
          <Logo collapsed={collapsed} />
          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={[selectedKey]}
            defaultOpenKeys={[openKey]}
            items={sidebarItems}
            onClick={({ key }) => router.push(key)}
            style={{ flex: 1, borderInlineEnd: "none", overflowY: "auto" }}
          />
          <SidebarProfile collapsed={collapsed} />
          <div
            onClick={() => setCollapsed((c) => !c)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: collapsed ? "center" : "flex-start",
              gap: 8,
              padding: "10px 20px",
              cursor: "pointer",
              color: "rgba(255,255,255,0.55)",
              fontSize: 12.5,
              borderTop: "1px solid rgba(255,255,255,0.08)",
            }}
          >
            {collapsed ? <DoubleRightOutlined /> : <DoubleLeftOutlined />}
            {!collapsed && <span>Thu gọn</span>}
          </div>
        </div>
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "0 24px",
            borderBottom: "1px solid #f0f0f0",
          }}
        >
          <Space size={16}>
            <span
              onClick={() => setCollapsed((c) => !c)}
              style={{ fontSize: 18, cursor: "pointer", color: "#555", display: "flex" }}
            >
              {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            </span>
            <Space size={8} style={{ fontSize: 18, fontWeight: 600, color: "#1f2937" }}>
              {parentTitle && (
                <>
                  <Text type="secondary" style={{ fontSize: 15, fontWeight: 400 }}>
                    {parentTitle}
                  </Text>
                  <Text type="secondary" style={{ fontWeight: 400 }}>
                    /
                  </Text>
                </>
              )}
              <span>{currentTitle}</span>
            </Space>
          </Space>

          <Space size={20} align="center">
            <Badge count={12} size="small">
              <BellOutlined style={{ fontSize: 18, color: "#555" }} />
            </Badge>
            <Badge count={5} size="small">
              <MessageOutlined style={{ fontSize: 18, color: "#555" }} />
            </Badge>
            <Dropdown menu={{ items: userMenuItems }} trigger={["click"]}>
              <Space size={10} style={{ cursor: "pointer" }}>
                <div style={{ textAlign: "right", lineHeight: 1.3 }}>
                  <div style={{ fontWeight: 500, fontSize: 13.5 }}>Nguyễn Văn A</div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Quản trị hệ thống
                  </Text>
                </div>
                <Avatar size={34} icon={<UserOutlined />} style={{ background: "#0B1739" }} />
                <DownOutlined style={{ fontSize: 11, color: "#999" }} />
              </Space>
            </Dropdown>
          </Space>
        </Header>
        <Content style={{ margin: 24 }}>{children}</Content>
        <Footer
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            color: "#999",
            fontSize: 13,
          }}
        >
          <span>© 2026 NGS Monitor. Bản quyền thuộc về DCV.</span>
          <span>Hỗ trợ: 1900 1234 | support@ngsmonitor.vn</span>
        </Footer>
      </Layout>
    </Layout>
  );
}
