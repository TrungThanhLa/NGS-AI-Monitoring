import { useState } from "react";
import { Layout, Menu, Avatar, Badge, Typography, Space, Button } from "antd";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import {
  DashboardOutlined,
  RadarChartOutlined,
  GlobalOutlined,
  FileTextOutlined,
  WarningOutlined,
  SafetyCertificateOutlined,
  BarChartOutlined,
  CalendarOutlined,
  SettingOutlined,
  UserOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  BellOutlined,
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
  { key: "/jobs", icon: <CalendarOutlined />, label: "Lịch chạy & Jobs" },
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

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

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

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        collapsible
        collapsed={collapsed}
        trigger={null}
        width={240}
        style={{ background: "#0A1D55", position: "fixed", height: "100vh", left: 0, top: 0, zIndex: 100, display: "flex", flexDirection: "column" }}
      >
        <div
          style={{
            height: 72,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: collapsed ? 8 : "0 18px",
            borderBottom: "1px solid rgba(255,255,255,0.1)",
            background: "rgba(0,0,0,0.15)",
            flexShrink: 0,
          }}
        >
          {!collapsed ? (
            <div
              style={{
                background: "#fff",
                borderRadius: 8,
                padding: "6px 12px",
                display: "flex",
                alignItems: "center",
                maxWidth: "100%",
              }}
            >
              <img src="/logo.jpg" alt="NGS" style={{ height: 40, width: "auto", display: "block" }} />
            </div>
          ) : (
            <div
              style={{
                background: "#fff",
                borderRadius: 8,
                width: 44,
                height: 44,
                overflow: "hidden",
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
              }}
            >
              <img
                src="/logo.jpg"
                alt="NGS"
                style={{
                  height: "220%",
                  width: "auto",
                  maxWidth: "none",
                  objectFit: "cover",
                  objectPosition: "left top",
                  display: "block",
                }}
              />
            </div>
          )}
        </div>

        <div style={{ overflowY: "auto", overflowX: "hidden", flex: 1, height: "calc(100vh - 72px)" }} className="ngs-sidebar-scroll">
          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={selectedKey}
            defaultOpenKeys={openKeys}
            items={MENU_ITEMS}
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
            <Space style={{ cursor: "default" }}>
              <Avatar style={{ background: "#00859A" }} size={32} icon={<UserOutlined />} />
              {!collapsed && (
                <Typography.Text strong style={{ color: "#0A1D55" }}>
                  Nguyễn Văn A
                </Typography.Text>
              )}
            </Space>
          </Space>
        </Header>

        <Content style={{ padding: 24, background: "#F5F7FA", minHeight: "calc(100vh - 64px)" }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
