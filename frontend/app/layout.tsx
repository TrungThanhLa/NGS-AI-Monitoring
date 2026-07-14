import "./globals.css";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import { ConfigProvider } from "antd";

export const metadata = {
  title: "NGS Monitor",
};

const theme = {
  token: {
    colorPrimary: "#0A5CC2",
    colorSuccess: "#10B981",
    colorWarning: "#F59E0B",
    borderRadius: 6,
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
