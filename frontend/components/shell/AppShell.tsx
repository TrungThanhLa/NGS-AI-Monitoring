"use client";

import { Layout, Menu, Badge, Avatar, Typography, Space } from "antd";
import { BellOutlined, MessageOutlined, UserOutlined } from "@ant-design/icons";
import { usePathname, useRouter } from "next/navigation";
import { sidebarItems } from "./menuConfig";

const { Sider, Header, Content, Footer } = Layout;
const { Text } = Typography;

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  const openKey = "/" + pathname.split("/")[1];
  const selectedKey = pathname.startsWith("/system") ? pathname : openKey;

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider width={240} theme="dark">
        <div
          style={{
            color: "#fff",
            fontWeight: 700,
            fontSize: 20,
            padding: "16px 24px",
            borderBottom: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          NGS
          <div style={{ fontSize: 11, fontWeight: 400, opacity: 0.7 }}>
            Minh bạch hóa mọi thông tin
          </div>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          defaultOpenKeys={[openKey]}
          items={sidebarItems}
          onClick={({ key }) => router.push(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            gap: 24,
            padding: "0 24px",
            borderBottom: "1px solid #f0f0f0",
          }}
        >
          <Badge count={12}>
            <BellOutlined style={{ fontSize: 18 }} />
          </Badge>
          <Badge count={5}>
            <MessageOutlined style={{ fontSize: 18 }} />
          </Badge>
          <Space>
            <Avatar icon={<UserOutlined />} />
            <div>
              <div style={{ fontWeight: 500, lineHeight: 1.2 }}>Nguyễn Văn A</div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Quản trị hệ thống
              </Text>
            </div>
          </Space>
        </Header>
        <Content style={{ margin: 24 }}>{children}</Content>
        <Footer style={{ textAlign: "center", color: "#999" }}>
          © 2026 NGS Monitor. Bản quyền thuộc về DCV.
        </Footer>
      </Layout>
    </Layout>
  );
}
