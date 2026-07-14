import "./globals.css";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import { ConfigProvider } from "antd";

export const metadata = {
  title: "NGS Monitor",
};

const theme = {
  token: {
    colorPrimary: "#2E6FF2",
    colorSuccess: "#10B981",
    colorWarning: "#F59E0B",
    borderRadius: 8,
  },
  components: {
    Layout: {
      siderBg: "#0B1739",
      headerBg: "#ffffff",
    },
    Menu: {
      darkItemBg: "#0B1739",
      darkSubMenuItemBg: "#0B1739",
      darkItemSelectedBg: "#2E6FF2",
      darkItemColor: "rgba(255,255,255,0.75)",
      darkItemHoverColor: "#ffffff",
    },
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body>
        <AntdRegistry>
          <ConfigProvider theme={theme}>{children}</ConfigProvider>
        </AntdRegistry>
      </body>
    </html>
  );
}
