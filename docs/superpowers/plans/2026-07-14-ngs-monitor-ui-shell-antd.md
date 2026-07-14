# NGS Monitor — AntD UI Shell (Hướng B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây lại giao diện `frontend/` theo đúng bố cục/màu sắc trong `ngs-monitoring-ui/NGS-Hình ảnh/` bằng Ant Design (Hướng B — viết lại toàn bộ bằng AntD, kể cả phần "Tạo báo cáo" hiện có), tích hợp thật duy nhất 2 tab "Báo cáo" (tạo báo cáo + lịch sử, dùng lại API sẵn có) và "Nguồn dữ liệu" (đọc `GET /api/sources`), các tab còn lại là giao diện tĩnh với dữ liệu mẫu.

**Architecture:** 1 route group `app/(shell)/` bọc toàn bộ trang bằng layout AntD (`Layout`/`Sider`/`Header`). Mọi trang mock dùng chung 1 component `MockStatPage` (DRY) để giảm lặp code. Phần "Báo cáo" giữ nguyên toàn bộ logic gọi API/polling/sessionStorage hiện có, chỉ viết lại lớp trình bày bằng AntD. Không sửa bất kỳ file backend nào.

**Tech Stack:** Next.js 14 (App Router) + React 18 + TypeScript (đã có) + Ant Design 5 + `@ant-design/nextjs-registry` (SSR cho AntD trong App Router) + `@ant-design/icons` + `recharts` (chỉ dùng cho 2 biểu đồ ở trang Tổng quan).

**Về kiểm thử:** Frontend hiện tại (`frontend/package.json`) không có test runner nào (không Jest/Vitest). Dự án không yêu cầu thêm test framework mới ở phạm vi này. Bước "verify" của mỗi task thay bằng: `npx tsc --noEmit` (kiểm tra type) + `npm run build` (kiểm tra build production không lỗi) + kiểm tra thủ công trên trình duyệt (`npm run dev`). Riêng tab "Báo cáo" bắt buộc kiểm thử thủ công với **job thật** (1 nguồn thật, VD VTV) trước khi coi Task 8 là xong, đúng yêu cầu `13-workflow.md` bước Commit.

---

## File Structure

```
frontend/
├── lib/
│   └── api.ts                              # (mới) API_BASE constant dùng chung
├── components/
│   ├── shell/
│   │   ├── menuConfig.tsx                  # (mới) khai báo menu sidebar (icon/label/route)
│   │   └── AppShell.tsx                    # (mới) Layout + Sider + Header dùng chung
│   ├── mock/
│   │   └── MockStatPage.tsx                # (mới) component tĩnh dùng chung cho các trang mock
│   ├── sources/
│   │   └── SourceListPage.tsx              # (mới) trang Nguồn dữ liệu — đọc API thật
│   └── reports/
│       ├── SourceSidebar.tsx               # (mới, thay components/SourceSidebar.tsx cũ) — AntD
│       ├── SummaryCard.tsx                 # (mới, thay components/SummaryCard.tsx cũ) — AntD
│       ├── CreateReportModal.tsx           # (mới) form tạo báo cáo — AntD, logic port từ app/page.tsx cũ
│       └── ReportHistoryTable.tsx          # (mới) bảng lịch sử — AntD, logic port từ app/history/page.tsx cũ
├── app/
│   ├── layout.tsx                          # (sửa) bọc AntdRegistry + ConfigProvider theme
│   ├── page.tsx                            # (sửa) redirect sang /dashboard
│   ├── (shell)/
│   │   ├── layout.tsx                      # (mới) dùng AppShell
│   │   ├── dashboard/page.tsx              # (mới) mock — có chart recharts
│   │   ├── campaigns/page.tsx              # (mới) mock
│   │   ├── sources/page.tsx                # (mới) thật
│   │   ├── contents/page.tsx               # (mới) mock
│   │   ├── alerts/page.tsx                 # (mới) mock
│   │   ├── cases/page.tsx                  # (mới) mock
│   │   ├── reports/page.tsx                # (mới) thật
│   │   ├── jobs/page.tsx                   # (mới) mock
│   │   └── system/
│   │       ├── page.tsx                    # (mới) mock — trang landing liệt kê 7 mục
│   │       ├── master-data/page.tsx        # (mới) mock
│   │       ├── users/page.tsx              # (mới) mock
│   │       ├── audit-logs/page.tsx         # (mới) mock
│   │       ├── alert-rules/page.tsx        # (mới) mock
│   │       ├── crawler-settings/page.tsx   # (mới) mock
│   │       ├── report-settings/page.tsx    # (mới) mock
│   │       └── settings/page.tsx           # (mới) mock
│   └── history/page.tsx                    # (xoá — gộp vào (shell)/reports)
├── components/SourceSidebar.tsx            # (xoá — thay bằng components/reports/SourceSidebar.tsx)
├── components/SummaryCard.tsx              # (xoá — thay bằng components/reports/SummaryCard.tsx)
├── tailwind.config.js                      # (sửa) tắt preflight tránh xung đột CSS với AntD
└── package.json                            # (sửa) thêm antd, @ant-design/nextjs-registry, @ant-design/icons, recharts
```

---

## Task 1: Cài đặt Ant Design + cấu hình nền tảng

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/tailwind.config.js`
- Create: `frontend/lib/api.ts`
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Cài dependency**

Run:
```bash
cd frontend
npm install antd @ant-design/nextjs-registry @ant-design/icons recharts
```

Expected: `package.json` có thêm 4 dependency, `package-lock.json` được tạo/cập nhật.

- [ ] **Step 2: Tắt Tailwind preflight để tránh xung đột CSS reset với AntD**

Sửa `frontend/tailwind.config.js`:

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {} },
  corePlugins: { preflight: false },
  plugins: [],
};
```

- [ ] **Step 3: Tạo `frontend/lib/api.ts`**

```ts
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
```

- [ ] **Step 4: Bọc AntdRegistry + ConfigProvider theme trong root layout**

Sửa `frontend/app/layout.tsx`:

```tsx
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
```

- [ ] **Step 5: Verify**

Run: `cd frontend && npx tsc --noEmit`
Expected: không lỗi type (AntD tự có type định nghĩa sẵn, không cần `@types/antd`).

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tailwind.config.js frontend/lib/api.ts frontend/app/layout.tsx
git commit -m "feat: cài Ant Design + ConfigProvider theme cho frontend"
```

---

## Task 2: Dựng khung Shell (Sidebar + Header)

**Files:**
- Create: `frontend/components/shell/menuConfig.tsx`
- Create: `frontend/components/shell/AppShell.tsx`
- Create: `frontend/app/(shell)/layout.tsx`

- [ ] **Step 1: Khai báo menu sidebar**

Tạo `frontend/components/shell/menuConfig.tsx`:

```tsx
import {
  HomeOutlined,
  AimOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  BellOutlined,
  FolderOutlined,
  FileDoneOutlined,
  ScheduleOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import type { MenuProps } from "antd";

export type MenuItem = Required<MenuProps>["items"][number];

export const sidebarItems: MenuItem[] = [
  { key: "/dashboard", icon: <HomeOutlined />, label: "Tổng quan" },
  { key: "/campaigns", icon: <AimOutlined />, label: "Chiến dịch giám sát" },
  { key: "/sources", icon: <DatabaseOutlined />, label: "Nguồn dữ liệu" },
  { key: "/contents", icon: <FileTextOutlined />, label: "Nội dung" },
  { key: "/alerts", icon: <BellOutlined />, label: "Cảnh báo" },
  { key: "/cases", icon: <FolderOutlined />, label: "Vụ việc" },
  { key: "/reports", icon: <FileDoneOutlined />, label: "Báo cáo" },
  { key: "/jobs", icon: <ScheduleOutlined />, label: "Lịch chạy & Jobs" },
  {
    key: "/system",
    icon: <SettingOutlined />,
    label: "Cấu hình hệ thống",
    children: [
      { key: "/system/master-data", label: "Dữ liệu dùng chung" },
      { key: "/system/users", label: "Người dùng & phân quyền" },
      { key: "/system/audit-logs", label: "Nhật ký hệ thống" },
      { key: "/system/alert-rules", label: "Cấu hình cảnh báo" },
      { key: "/system/crawler-settings", label: "Cấu hình Crawler" },
      { key: "/system/report-settings", label: "Cấu hình báo cáo" },
      { key: "/system/settings", label: "Tham số hệ thống" },
    ],
  },
];
```

- [ ] **Step 2: Tạo `AppShell.tsx`**

```tsx
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
```

- [ ] **Step 3: Tạo `frontend/app/(shell)/layout.tsx`**

```tsx
import AppShell from "@/components/shell/AppShell";

export default function ShellLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
```

- [ ] **Step 4: Sửa `frontend/app/page.tsx` để redirect sang `/dashboard`**

```tsx
import { redirect } from "next/navigation";

export default function RootPage() {
  redirect("/dashboard");
}
```

- [ ] **Step 5: Verify**

Run: `cd frontend && npx tsc --noEmit`
Expected: lỗi "Cannot find module '@/app/(shell)/dashboard/page'" hoặc tương tự vì trang `/dashboard` chưa tồn tại — đây là lỗi mong đợi ở bước này, sẽ hết sau Task 3. Nếu `tsc --noEmit` không tự resolve route file (Next.js không cần file đó tồn tại để type-check các file khác) thì đảm bảo không có lỗi nào **ngoài** việc thiếu trang đích.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/shell frontend/app/\(shell\)/layout.tsx frontend/app/page.tsx
git commit -m "feat: dựng khung Sidebar + Header AntD dùng chung cho toàn app"
```

---

## Task 3: Component mock dùng chung + 6 trang mock đơn giản

**Files:**
- Create: `frontend/components/mock/MockStatPage.tsx`
- Create: `frontend/app/(shell)/campaigns/page.tsx`
- Create: `frontend/app/(shell)/contents/page.tsx`
- Create: `frontend/app/(shell)/alerts/page.tsx`
- Create: `frontend/app/(shell)/cases/page.tsx`
- Create: `frontend/app/(shell)/jobs/page.tsx`
- Create: `frontend/app/(shell)/system/page.tsx`

- [ ] **Step 1: Tạo component dùng chung `MockStatPage.tsx`**

```tsx
"use client";

import { Card, Col, Row, Statistic, Table, Typography, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";

export type StatItem = {
  title: string;
  value: number | string;
  suffix?: string;
};

type Props<T extends object> = {
  title: string;
  description?: string;
  stats?: StatItem[];
  columns: ColumnsType<T>;
  dataSource: T[];
  rowKey: keyof T;
};

export default function MockStatPage<T extends object>({
  title,
  description,
  stats,
  columns,
  dataSource,
  rowKey,
}: Props<T>) {
  return (
    <div>
      <Typography.Title level={3}>{title}</Typography.Title>
      {description && (
        <Typography.Paragraph type="secondary">{description}</Typography.Paragraph>
      )}
      {stats && stats.length > 0 && (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          {stats.map((s) => (
            <Col span={24 / stats.length} key={s.title}>
              <Card>
                <Statistic title={s.title} value={s.value} suffix={s.suffix} />
              </Card>
            </Col>
          ))}
        </Row>
      )}
      <Card>
        <Table
          columns={columns}
          dataSource={dataSource}
          rowKey={rowKey as string}
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </div>
  );
}

export { Tag };
```

- [ ] **Step 2: Trang Chiến dịch giám sát (mock)**

Tạo `frontend/app/(shell)/campaigns/page.tsx`:

```tsx
"use client";

import { Tag } from "antd";
import MockStatPage from "@/components/mock/MockStatPage";

type Campaign = {
  id: string;
  code: string;
  name: string;
  owner: string;
  status: "Đang chạy" | "Tạm dừng" | "Nháp";
  sourceCount: number;
  contentCount: number;
};

const data: Campaign[] = [
  { id: "1", code: "CD001", name: "Giám sát tin giả Quý 3", owner: "Nguyễn Văn A", status: "Đang chạy", sourceCount: 7, contentCount: 1284 },
  { id: "2", code: "CD002", name: "Giám sát lừa đảo trực tuyến", owner: "Trần Thị B", status: "Đang chạy", sourceCount: 5, contentCount: 852 },
  { id: "3", code: "CD003", name: "Giám sát Deepfake", owner: "Lê Văn C", status: "Tạm dừng", sourceCount: 3, contentCount: 210 },
];

const statusColor: Record<Campaign["status"], string> = {
  "Đang chạy": "green",
  "Tạm dừng": "orange",
  "Nháp": "default",
};

export default function CampaignsPage() {
  return (
    <MockStatPage<Campaign>
      title="Chiến dịch giám sát"
      stats={[
        { title: "Tổng chiến dịch", value: data.length },
        { title: "Đang chạy", value: data.filter((c) => c.status === "Đang chạy").length },
        { title: "Tổng nội dung", value: data.reduce((s, c) => s + c.contentCount, 0) },
      ]}
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Mã", dataIndex: "code" },
        { title: "Tên chiến dịch", dataIndex: "name" },
        { title: "Người phụ trách", dataIndex: "owner" },
        { title: "Số nguồn", dataIndex: "sourceCount" },
        { title: "Số nội dung", dataIndex: "contentCount" },
        {
          title: "Trạng thái",
          dataIndex: "status",
          render: (status: Campaign["status"]) => <Tag color={statusColor[status]}>{status}</Tag>,
        },
      ]}
    />
  );
}
```

- [ ] **Step 3: Trang Nội dung (mock)**

Tạo `frontend/app/(shell)/contents/page.tsx`:

```tsx
"use client";

import { Tag } from "antd";
import MockStatPage from "@/components/mock/MockStatPage";

type ContentRow = {
  id: string;
  title: string;
  source: string;
  platform: string;
  publishedAt: string;
  sentiment: "Tích cực" | "Trung tính" | "Tiêu cực";
};

const data: ContentRow[] = [
  { id: "1", title: "Cảnh báo chiêu trò giả mạo ngân hàng", source: "VTV News", platform: "Website", publishedAt: "14/07/2026", sentiment: "Tiêu cực" },
  { id: "2", title: "Hướng dẫn nhận diện tin giả trên mạng xã hội", source: "VOV", platform: "Website", publishedAt: "13/07/2026", sentiment: "Tích cực" },
  { id: "3", title: "Thông tin chính sách mới về an toàn thông tin", source: "CAND", platform: "Website", publishedAt: "12/07/2026", sentiment: "Trung tính" },
];

const sentimentColor: Record<ContentRow["sentiment"], string> = {
  "Tích cực": "green",
  "Trung tính": "default",
  "Tiêu cực": "red",
};

export default function ContentsPage() {
  return (
    <MockStatPage<ContentRow>
      title="Nội dung thu thập"
      stats={[
        { title: "Tổng nội dung", value: 128456 },
        { title: "Hôm nay", value: 2845 },
      ]}
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Tiêu đề", dataIndex: "title" },
        { title: "Nguồn", dataIndex: "source" },
        { title: "Nền tảng", dataIndex: "platform" },
        { title: "Thời gian đăng", dataIndex: "publishedAt" },
        {
          title: "Sentiment",
          dataIndex: "sentiment",
          render: (s: ContentRow["sentiment"]) => <Tag color={sentimentColor[s]}>{s}</Tag>,
        },
      ]}
    />
  );
}
```

- [ ] **Step 4: Trang Cảnh báo (mock)**

Tạo `frontend/app/(shell)/alerts/page.tsx`:

```tsx
"use client";

import { Tag } from "antd";
import MockStatPage from "@/components/mock/MockStatPage";

type AlertRow = {
  id: string;
  title: string;
  type: string;
  level: "Thấp" | "Trung bình" | "Cao" | "Rất cao";
  createdAt: string;
};

const data: AlertRow[] = [
  { id: "1", title: "Từ khóa \"deepfake\" tăng đột biến 350%", type: "Từ khóa", level: "Rất cao", createdAt: "14/07/2026 10:23" },
  { id: "2", title: "Xuất hiện thông tin giả mạo Bộ Công an", type: "Giả mạo", level: "Cao", createdAt: "14/07/2026 09:41" },
  { id: "3", title: "Nhiều bài viết tiêu cực về chính sách mới", type: "Sentiment", level: "Trung bình", createdAt: "14/07/2026 08:55" },
];

const levelColor: Record<AlertRow["level"], string> = {
  "Thấp": "blue",
  "Trung bình": "gold",
  "Cao": "orange",
  "Rất cao": "red",
};

export default function AlertsPage() {
  return (
    <MockStatPage<AlertRow>
      title="Cảnh báo"
      stats={[{ title: "Cảnh báo mới", value: 18 }]}
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Tiêu đề cảnh báo", dataIndex: "title" },
        { title: "Loại cảnh báo", dataIndex: "type" },
        {
          title: "Mức độ",
          dataIndex: "level",
          render: (level: AlertRow["level"]) => <Tag color={levelColor[level]}>{level}</Tag>,
        },
        { title: "Thời gian tạo", dataIndex: "createdAt" },
      ]}
    />
  );
}
```

- [ ] **Step 5: Trang Vụ việc (mock)**

Tạo `frontend/app/(shell)/cases/page.tsx`:

```tsx
"use client";

import { Tag } from "antd";
import MockStatPage from "@/components/mock/MockStatPage";

type CaseRow = {
  id: string;
  code: string;
  name: string;
  priority: "Thấp" | "Trung bình" | "Cao";
  status: "Mới phát hiện" | "Đang xác minh" | "Đang xử lý" | "Đã xử lý";
  owner: string;
};

const data: CaseRow[] = [
  { id: "1", code: "VV001", name: "Giả mạo website dịch vụ công trực tuyến", priority: "Cao", status: "Đang xử lý", owner: "Nguyễn Văn A" },
  { id: "2", code: "VV002", name: "Lừa đảo tuyển dụng qua mạng xã hội", priority: "Trung bình", status: "Đang xác minh", owner: "Trần Thị B" },
];

const statusColor: Record<CaseRow["status"], string> = {
  "Mới phát hiện": "default",
  "Đang xác minh": "gold",
  "Đang xử lý": "blue",
  "Đã xử lý": "green",
};

export default function CasesPage() {
  return (
    <MockStatPage<CaseRow>
      title="Vụ việc"
      stats={[{ title: "Vụ việc đang xử lý", value: 27 }]}
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Mã vụ việc", dataIndex: "code" },
        { title: "Tên vụ việc", dataIndex: "name" },
        { title: "Người phụ trách", dataIndex: "owner" },
        {
          title: "Trạng thái",
          dataIndex: "status",
          render: (s: CaseRow["status"]) => <Tag color={statusColor[s]}>{s}</Tag>,
        },
      ]}
    />
  );
}
```

- [ ] **Step 6: Trang Lịch chạy & Jobs (mock)**

Tạo `frontend/app/(shell)/jobs/page.tsx`:

```tsx
"use client";

import { Tag } from "antd";
import MockStatPage from "@/components/mock/MockStatPage";

type JobRow = {
  id: string;
  code: string;
  type: "Crawl" | "AI" | "Report";
  source: string;
  status: "Đang chạy" | "Hoàn thành" | "Lỗi";
  startedAt: string;
};

const data: JobRow[] = [
  { id: "1", code: "JOB-0231", type: "Crawl", source: "VTV News", status: "Hoàn thành", startedAt: "14/07/2026 08:00" },
  { id: "2", code: "JOB-0232", type: "AI", source: "VOV", status: "Đang chạy", startedAt: "14/07/2026 09:10" },
];

const statusColor: Record<JobRow["status"], string> = {
  "Đang chạy": "blue",
  "Hoàn thành": "green",
  "Lỗi": "red",
};

export default function JobsPage() {
  return (
    <MockStatPage<JobRow>
      title="Lịch chạy & Jobs"
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Mã Job", dataIndex: "code" },
        { title: "Loại Job", dataIndex: "type" },
        { title: "Nguồn", dataIndex: "source" },
        {
          title: "Trạng thái",
          dataIndex: "status",
          render: (s: JobRow["status"]) => <Tag color={statusColor[s]}>{s}</Tag>,
        },
        { title: "Bắt đầu", dataIndex: "startedAt" },
      ]}
    />
  );
}
```

- [ ] **Step 7: Trang landing Cấu hình hệ thống (mock)**

Tạo `frontend/app/(shell)/system/page.tsx`:

```tsx
"use client";

import { Card, Col, Row, Typography } from "antd";
import Link from "next/link";

const items = [
  { href: "/system/master-data", title: "Dữ liệu dùng chung", desc: "Quản lý nhóm nguồn, nền tảng, chủ đề, từ khóa dùng chung" },
  { href: "/system/users", title: "Người dùng & phân quyền", desc: "Quản lý tài khoản, nhóm quyền" },
  { href: "/system/audit-logs", title: "Nhật ký hệ thống", desc: "Lịch sử thao tác trên hệ thống" },
  { href: "/system/alert-rules", title: "Cấu hình cảnh báo", desc: "Thiết lập ngưỡng và quy tắc sinh cảnh báo" },
  { href: "/system/crawler-settings", title: "Cấu hình Crawler", desc: "Thiết lập tham số thu thập dữ liệu" },
  { href: "/system/report-settings", title: "Cấu hình báo cáo", desc: "Thiết lập mẫu và hiển thị báo cáo" },
  { href: "/system/settings", title: "Tham số hệ thống", desc: "Cấu hình bảo mật, phiên đăng nhập" },
];

export default function SystemPage() {
  return (
    <div>
      <Typography.Title level={3}>Cấu hình hệ thống</Typography.Title>
      <Row gutter={[16, 16]}>
        {items.map((item) => (
          <Col span={8} key={item.href}>
            <Link href={item.href}>
              <Card hoverable title={item.title}>
                {item.desc}
              </Card>
            </Link>
          </Col>
        ))}
      </Row>
    </div>
  );
}
```

- [ ] **Step 8: Verify**

Run: `cd frontend && npx tsc --noEmit`
Expected: không lỗi type.

- [ ] **Step 9: Commit**

```bash
git add frontend/components/mock frontend/app/\(shell\)/campaigns frontend/app/\(shell\)/contents frontend/app/\(shell\)/alerts frontend/app/\(shell\)/cases frontend/app/\(shell\)/jobs frontend/app/\(shell\)/system/page.tsx
git commit -m "feat: thêm component mock dùng chung + 6 trang giao diện tĩnh"
```

---

## Task 4: Trang Tổng quan (Dashboard, mock có biểu đồ)

**Files:**
- Create: `frontend/app/(shell)/dashboard/page.tsx`

- [ ] **Step 1: Viết trang Dashboard**

```tsx
"use client";

import { Card, Col, Row, Statistic, List, Tag } from "antd";
import {
  FileTextOutlined,
  GlobalOutlined,
  WarningOutlined,
  FolderOutlined,
  RiseOutlined,
} from "@ant-design/icons";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const trendData = [
  { date: "01/01", value: 3200 },
  { date: "15/01", value: 4100 },
  { date: "29/01", value: 3800 },
  { date: "12/02", value: 5200 },
  { date: "26/02", value: 4600 },
  { date: "12/03", value: 5100 },
  { date: "26/03", value: 6842 },
  { date: "09/04", value: 6100 },
];

const platformData = [
  { name: "Facebook", value: 58246 },
  { name: "Website", value: 28461 },
  { name: "TikTok", value: 20314 },
  { name: "YouTube", value: 15872 },
  { name: "Zalo", value: 5563 },
];

const platformColors = ["#0A5CC2", "#10B981", "#6366F1", "#94A3B8", "#F59E0B"];

const topTopics = [
  { name: "Tin giả và thông tin sai lệch", percent: 25.2 },
  { name: "Lừa đảo, giả mạo", percent: 19.6 },
  { name: "Giải thích chính sách", percent: 14.6 },
];

const latestAlerts = [
  { level: "Rất cao", text: 'Từ khóa "deepfake" tăng đột biến 350%' },
  { level: "Cao", text: "Xuất hiện thông tin giả mạo Bộ Công an" },
  { level: "Trung bình", text: "Nhiều bài viết tiêu cực về chính sách mới" },
];

const levelColor: Record<string, string> = {
  "Rất cao": "red",
  "Cao": "orange",
  "Trung bình": "gold",
};

export default function DashboardPage() {
  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={5}>
          <Card>
            <Statistic title="Tổng số nội dung" value={128456} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="Nội dung hôm nay" value={2845} prefix={<GlobalOutlined />} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="Cảnh báo mới" value={18} prefix={<WarningOutlined />} valueStyle={{ color: "#cf1322" }} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="Vụ việc đang xử lý" value={27} prefix={<FolderOutlined />} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="Mức độ quan tâm cao" value={156} prefix={<RiseOutlined />} />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={16}>
          <Card title="Diễn biến số lượng nội dung theo thời gian">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={trendData}>
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#0A5CC2" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col span={8}>
          <Card title="Nội dung theo nền tảng">
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={platformData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={90}>
                  {platformData.map((entry, index) => (
                    <Cell key={entry.name} fill={platformColors[index % platformColors.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="Top chủ đề nổi bật">
            <List
              dataSource={topTopics}
              renderItem={(item) => (
                <List.Item>
                  {item.name} — {item.percent}%
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Cảnh báo mới nhất">
            <List
              dataSource={latestAlerts}
              renderItem={(item) => (
                <List.Item>
                  <Tag color={levelColor[item.level]}>{item.level}</Tag> {item.text}
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc --noEmit`
Expected: không lỗi type.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(shell\)/dashboard
git commit -m "feat: thêm trang Tổng quan (dashboard mock) với biểu đồ recharts"
```

---

## Task 5: 7 trang con "Cấu hình hệ thống" (mock, phẳng — không tab con)

**Files:**
- Create: `frontend/app/(shell)/system/master-data/page.tsx`
- Create: `frontend/app/(shell)/system/users/page.tsx`
- Create: `frontend/app/(shell)/system/audit-logs/page.tsx`
- Create: `frontend/app/(shell)/system/alert-rules/page.tsx`
- Create: `frontend/app/(shell)/system/crawler-settings/page.tsx`
- Create: `frontend/app/(shell)/system/report-settings/page.tsx`
- Create: `frontend/app/(shell)/system/settings/page.tsx`

- [ ] **Step 1: Dữ liệu dùng chung (mock danh mục Chủ đề — đại diện cho cả nhóm "dữ liệu dùng chung")**

Tạo `frontend/app/(shell)/system/master-data/page.tsx`:

```tsx
"use client";

import { Tag } from "antd";
import MockStatPage from "@/components/mock/MockStatPage";

type Topic = {
  id: string;
  code: string;
  name: string;
  status: "Đang sử dụng" | "Tạm ngưng";
};

const data: Topic[] = [
  { id: "1", code: "TOPIC_01", name: "Tin giả và thông tin sai lệch", status: "Đang sử dụng" },
  { id: "2", code: "TOPIC_02", name: "Phản bác, đính chính thông tin", status: "Đang sử dụng" },
  { id: "3", code: "TOPIC_03", name: "Kiểm chứng và xác thực thông tin", status: "Đang sử dụng" },
  { id: "4", code: "TOPIC_04", name: "Giải thích chính sách và cung cấp thông tin chính thống", status: "Đang sử dụng" },
  { id: "5", code: "TOPIC_05", name: "Cảnh báo lừa đảo, giả mạo trên không gian mạng", status: "Đang sử dụng" },
  { id: "6", code: "TOPIC_06", name: "AI, Deepfake và công nghệ tạo sinh", status: "Đang sử dụng" },
  { id: "7", code: "TOPIC_07", name: "An toàn thông tin và an ninh mạng", status: "Đang sử dụng" },
  { id: "8", code: "TOPIC_08", name: "Hướng dẫn nhận diện tin giả và nâng cao kỹ năng truyền thông số", status: "Đang sử dụng" },
];

export default function MasterDataPage() {
  return (
    <MockStatPage<Topic>
      title="Dữ liệu dùng chung — Chủ đề"
      description="Danh mục 8 nhóm chủ đề dùng cho phân loại AI (backend/ai/prompts/v1.py). Trang này chỉ minh hoạ giao diện, chưa CRUD thật."
      stats={[{ title: "Tổng số chủ đề", value: data.length }]}
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Mã", dataIndex: "code" },
        { title: "Tên chủ đề", dataIndex: "name" },
        {
          title: "Trạng thái",
          dataIndex: "status",
          render: (s: Topic["status"]) => <Tag color={s === "Đang sử dụng" ? "green" : "default"}>{s}</Tag>,
        },
      ]}
    />
  );
}
```

- [ ] **Step 2: Người dùng & phân quyền**

Tạo `frontend/app/(shell)/system/users/page.tsx`:

```tsx
"use client";

import { Tag } from "antd";
import MockStatPage from "@/components/mock/MockStatPage";

type UserRow = {
  id: string;
  name: string;
  username: string;
  email: string;
  role: string;
  status: "Hoạt động" | "Khoá";
};

const data: UserRow[] = [
  { id: "1", name: "Nguyễn Văn A", username: "vana", email: "vana@ngsmonitor.vn", role: "Admin", status: "Hoạt động" },
  { id: "2", name: "Trần Thị B", username: "thib", email: "thib@ngsmonitor.vn", role: "Analyst", status: "Hoạt động" },
];

export default function UsersPage() {
  return (
    <MockStatPage<UserRow>
      title="Người dùng & phân quyền"
      description="Hệ thống hiện tại chưa có auth/RBAC thật — trang này chỉ minh hoạ giao diện."
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Họ tên", dataIndex: "name" },
        { title: "Tên đăng nhập", dataIndex: "username" },
        { title: "Email", dataIndex: "email" },
        { title: "Nhóm quyền", dataIndex: "role" },
        {
          title: "Trạng thái",
          dataIndex: "status",
          render: (s: UserRow["status"]) => <Tag color={s === "Hoạt động" ? "green" : "red"}>{s}</Tag>,
        },
      ]}
    />
  );
}
```

- [ ] **Step 3: Nhật ký hệ thống**

Tạo `frontend/app/(shell)/system/audit-logs/page.tsx`:

```tsx
"use client";

import MockStatPage from "@/components/mock/MockStatPage";

type LogRow = {
  id: string;
  user: string;
  action: string;
  object: string;
  time: string;
};

const data: LogRow[] = [
  { id: "1", user: "Nguyễn Văn A", action: "Tạo báo cáo", object: "JOB-0231", time: "14/07/2026 08:00" },
  { id: "2", user: "Trần Thị B", action: "Đăng nhập", object: "-", time: "14/07/2026 07:50" },
];

export default function AuditLogsPage() {
  return (
    <MockStatPage<LogRow>
      title="Nhật ký hệ thống"
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Người dùng", dataIndex: "user" },
        { title: "Hành động", dataIndex: "action" },
        { title: "Đối tượng", dataIndex: "object" },
        { title: "Thời gian", dataIndex: "time" },
      ]}
    />
  );
}
```

- [ ] **Step 4: Cấu hình cảnh báo**

Tạo `frontend/app/(shell)/system/alert-rules/page.tsx`:

```tsx
"use client";

import MockStatPage from "@/components/mock/MockStatPage";

type RuleRow = {
  id: string;
  name: string;
  condition: string;
  level: string;
};

const data: RuleRow[] = [
  { id: "1", name: "Từ khóa tăng đột biến", condition: "Tăng > 200% trong 1 giờ", level: "Rất cao" },
  { id: "2", name: "Sentiment tiêu cực tăng nhanh", condition: "Tỉ lệ tiêu cực > 60%", level: "Cao" },
];

export default function AlertRulesPage() {
  return (
    <MockStatPage<RuleRow>
      title="Cấu hình cảnh báo"
      rowKey="id"
      dataSource={data}
      columns={[
        { title: "Tên quy tắc", dataIndex: "name" },
        { title: "Điều kiện", dataIndex: "condition" },
        { title: "Mức độ", dataIndex: "level" },
      ]}
    />
  );
}
```

- [ ] **Step 5: Cấu hình Crawler**

Tạo `frontend/app/(shell)/system/crawler-settings/page.tsx`:

```tsx
"use client";

import { Card, Form, InputNumber, Switch, Typography, Row, Col } from "antd";

export default function CrawlerSettingsPage() {
  return (
    <div>
      <Typography.Title level={3}>Cấu hình Crawler</Typography.Title>
      <Typography.Paragraph type="secondary">
        Các tham số dưới đây hiện đang là biến môi trường (`CRAWLER_DELAY_SECONDS`, `CRAWLER_MAX_RETRIES`,
        `CRAWLER_TIMEOUT_SECONDS`) — form này chỉ minh hoạ giao diện, chưa lưu được thật.
      </Typography.Paragraph>
      <Card>
        <Form layout="vertical">
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="Delay giữa các request (giây)">
                <InputNumber style={{ width: "100%" }} defaultValue={1.5} min={0} step={0.5} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="Số lần thử lại khi lỗi (retry_count)">
                <InputNumber style={{ width: "100%" }} defaultValue={3} min={0} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="Thời gian chờ mỗi request (giây)">
                <InputNumber style={{ width: "100%" }} defaultValue={30} min={1} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="Tuân thủ robots.txt" valuePropName="checked">
            <Switch defaultChecked />
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
```

- [ ] **Step 6: Cấu hình báo cáo**

Tạo `frontend/app/(shell)/system/report-settings/page.tsx`:

```tsx
"use client";

import { Card, Form, Input, Typography } from "antd";

export default function ReportSettingsPage() {
  return (
    <div>
      <Typography.Title level={3}>Cấu hình báo cáo</Typography.Title>
      <Typography.Paragraph type="secondary">
        Mẫu báo cáo DOCX hiện tại là file tĩnh (`templates/report_template.docx`) — form này chỉ minh hoạ
        giao diện, chưa lưu được thật.
      </Typography.Paragraph>
      <Card>
        <Form layout="vertical">
          <Form.Item label="Tên tổ chức">
            <Input defaultValue="Cục An ninh mạng và phòng, chống tội phạm sử dụng công nghệ cao" />
          </Form.Item>
          <Form.Item label="Đơn vị báo cáo">
            <Input defaultValue="Phòng Giám sát không gian mạng" />
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
```

- [ ] **Step 7: Tham số hệ thống**

Tạo `frontend/app/(shell)/system/settings/page.tsx`:

```tsx
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
```

- [ ] **Step 8: Verify**

Run: `cd frontend && npx tsc --noEmit`
Expected: không lỗi type.

- [ ] **Step 9: Commit**

```bash
git add frontend/app/\(shell\)/system
git commit -m "feat: thêm 7 trang con Cấu hình hệ thống (mock, phẳng)"
```

---

## Task 6: Trang Nguồn dữ liệu (thật — đọc `GET /api/sources`)

**Files:**
- Create: `frontend/components/sources/SourceListPage.tsx`
- Create: `frontend/app/(shell)/sources/page.tsx`

- [ ] **Step 1: Viết component đọc dữ liệu thật**

Tạo `frontend/components/sources/SourceListPage.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Button, Card, Table, Tag, Tooltip, Typography } from "antd";
import { API_BASE } from "@/lib/api";

type Source = {
  source_id: string;
  name: string;
  domain: string;
  group_name: string;
  is_active: boolean;
};

export default function SourceListPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/sources`)
      .then((res) => (res.ok ? res.json() : { sources: [] }))
      .then((data) => setSources(data.sources ?? []))
      .catch(() => setSources([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <Typography.Title level={3}>Nguồn dữ liệu</Typography.Title>
      <Card
        extra={
          <Tooltip title="Chưa triển khai — CRUD nguồn qua UI thuộc phạm vi Slice 6, chưa code">
            <Button type="primary" disabled>
              Thêm nguồn
            </Button>
          </Tooltip>
        }
      >
        <Table<Source>
          loading={loading}
          rowKey="source_id"
          dataSource={sources}
          columns={[
            { title: "Tên nguồn", dataIndex: "name" },
            { title: "Nhóm nguồn", dataIndex: "group_name" },
            { title: "Domain", dataIndex: "domain" },
            {
              title: "Trạng thái",
              dataIndex: "is_active",
              render: (active: boolean) => <Tag color={active ? "green" : "default"}>{active ? "Đang hoạt động" : "Tắt"}</Tag>,
            },
            {
              title: "Hành động",
              render: () => (
                <Tooltip title="Chưa triển khai">
                  <Button size="small" disabled>
                    Sửa
                  </Button>
                </Tooltip>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Trang route**

Tạo `frontend/app/(shell)/sources/page.tsx`:

```tsx
import SourceListPage from "@/components/sources/SourceListPage";

export default function SourcesPage() {
  return <SourceListPage />;
}
```

- [ ] **Step 3: Verify với backend thật**

Run: `cd frontend && npm run dev` (đảm bảo backend đang chạy ở `http://localhost:8000`, có `NEXT_PUBLIC_API_BASE_URL` trỏ đúng nếu khác mặc định)
Mở `http://localhost:3000/sources` trên trình duyệt.
Expected: bảng hiển thị đúng 7 nguồn thật đã seed trong DB (VTV, VOV, VietnamPlus, CAND, BoCongAn, TinGia, Vietnam.vn), nút "Thêm nguồn"/"Sửa" bị mờ (disabled) kèm tooltip khi hover.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/sources frontend/app/\(shell\)/sources
git commit -m "feat: thêm trang Nguồn dữ liệu đọc API thật GET /api/sources"
```

---

## Task 7: Viết lại `SourceSidebar` + `SummaryCard` bằng AntD

**Files:**
- Create: `frontend/components/reports/SourceSidebar.tsx`
- Create: `frontend/components/reports/SummaryCard.tsx`
- Delete: `frontend/components/SourceSidebar.tsx`
- Delete: `frontend/components/SummaryCard.tsx`

- [ ] **Step 1: Viết `components/reports/SourceSidebar.tsx`**

Giữ nguyên toàn bộ logic lọc/group hiện có (`components/SourceSidebar.tsx` cũ), chỉ đổi JSX sang AntD:

```tsx
"use client";

import { useMemo, useState } from "react";
import { Input, Checkbox, Tag, Typography } from "antd";
import { SearchOutlined } from "@ant-design/icons";

export type SourceItem = {
  source_id: string;
  name: string;
  domain: string;
  group_name: string;
};

type Props = {
  sources: SourceItem[];
  selectedIds: string[];
  onToggle: (sourceId: string) => void;
};

export default function SourceSidebar({ sources, selectedIds, onToggle }: Props) {
  const [search, setSearch] = useState("");

  const filtered = useMemo(
    () => sources.filter((s) => s.name.toLowerCase().includes(search.toLowerCase())),
    [sources, search]
  );

  const grouped = useMemo(() => {
    const groups = new Map<string, SourceItem[]>();
    for (const source of filtered) {
      const list = groups.get(source.group_name) ?? [];
      list.push(source);
      groups.set(source.group_name, list);
    }
    return Array.from(groups.entries());
  }, [filtered]);

  const selectedSources = sources.filter((s) => selectedIds.includes(s.source_id));

  return (
    <div style={{ border: "1px solid #f0f0f0", borderRadius: 8, padding: 12 }}>
      <Input
        prefix={<SearchOutlined />}
        placeholder="Tìm nguồn..."
        aria-label="Tìm nguồn"
        style={{ marginBottom: 12 }}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {selectedSources.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          {selectedSources.map((s) => (
            <Tag key={s.source_id} closable onClose={() => onToggle(s.source_id)} color="blue">
              {s.name}
            </Tag>
          ))}
        </div>
      )}

      {grouped.map(([groupName, items]) => (
        <div key={groupName} style={{ marginBottom: 12 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12, fontWeight: 500 }}>
            {groupName}
          </Typography.Text>
          <div style={{ marginTop: 4 }}>
            {items.map((source) => (
              <div key={source.source_id} style={{ padding: "2px 0" }}>
                <Checkbox
                  checked={selectedIds.includes(source.source_id)}
                  onChange={() => onToggle(source.source_id)}
                >
                  {source.name}
                </Checkbox>
              </div>
            ))}
          </div>
        </div>
      ))}

      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {selectedIds.length}/{sources.length} đã chọn
      </Typography.Text>
    </div>
  );
}
```

- [ ] **Step 2: Viết `components/reports/SummaryCard.tsx`**

```tsx
import { Card, Alert, Typography } from "antd";

type Props = {
  sourceCount: number;
  dayCount: number;
};

export default function SummaryCard({ sourceCount, dayCount }: Props) {
  const showWarning = sourceCount >= 5 && dayCount >= 60;

  return (
    <Card size="small" style={{ background: "#fafafa" }}>
      <Typography.Text strong>
        {sourceCount} nguồn · {dayCount} ngày
      </Typography.Text>
      {showWarning && (
        <Alert
          style={{ marginTop: 8 }}
          type="warning"
          showIcon
          message="Job sẽ chạy nền, có thể mất nhiều thời gian với số nguồn/ngày lớn — sẽ thông báo khi xong."
        />
      )}
    </Card>
  );
}
```

- [ ] **Step 3: Xoá component cũ**

```bash
cd frontend
rm components/SourceSidebar.tsx components/SummaryCard.tsx
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npx tsc --noEmit`
Expected: sẽ có lỗi "Cannot find module '@/components/SourceSidebar'" trong `app/page.tsx` cũ — đây là lỗi mong đợi, sẽ hết khi `app/page.tsx` được thay bằng redirect ở Task 2 Step 4 (đã làm) và `app/history/page.tsx` bị xoá ở Task 8. Xác nhận không còn file nào khác import 2 component cũ (`grep -r "@/components/SourceSidebar\"" frontend/app` và tương tự cho SummaryCard) ngoài các file sẽ bị xoá/thay ở Task 8.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/reports/SourceSidebar.tsx frontend/components/reports/SummaryCard.tsx
git rm frontend/components/SourceSidebar.tsx frontend/components/SummaryCard.tsx
git commit -m "feat: viết lại SourceSidebar + SummaryCard bằng Ant Design"
```

---

## Task 8: Tab "Báo cáo" thật (gộp tạo báo cáo + lịch sử)

**Files:**
- Create: `frontend/components/reports/CreateReportModal.tsx`
- Create: `frontend/components/reports/ReportHistoryTable.tsx`
- Create: `frontend/app/(shell)/reports/page.tsx`
- Delete: `frontend/app/history/page.tsx`
- Delete: `frontend/app/page.tsx` cũ đã xử lý ở Task 2 (chỉ xác nhận lại)

- [ ] **Step 1: Viết `CreateReportModal.tsx` — port nguyên logic từ `app/page.tsx` cũ**

```tsx
"use client";

import { useEffect, useState } from "react";
import { Modal, Button, DatePicker, Space, Table, Tag, Alert, Progress, Popconfirm, Typography } from "antd";
import dayjs, { Dayjs } from "dayjs";
import { API_BASE } from "@/lib/api";
import SourceSidebar, { SourceItem } from "./SourceSidebar";
import SummaryCard from "./SummaryCard";

const JOB_ID_STORAGE_KEY = "ngs_monitor_job_id";

const DATE_PRESETS = [
  { label: "Hôm nay", days: 0 },
  { label: "7 ngày", days: 7 },
  { label: "30 ngày", days: 30 },
  { label: "90 ngày", days: 90 },
  { label: "150 ngày", days: 150 },
];

function todayMinus(days: number): Dayjs {
  return dayjs().subtract(days, "day");
}

type JobStatus = {
  job_id: string;
  status: string;
  progress: { crawled: number; analyzed: number; total_estimated: number };
  error_log?: string;
};

type CrawledArticle = {
  title: string | null;
  url: string;
  status: string;
  source_name: string | null;
  crawl_duration_seconds: number | null;
  analysis_duration_seconds: number | null;
  total_duration_seconds: number | null;
};

function formatSeconds(value: number | null): string {
  return value === null ? "-" : `${value.toFixed(1)}s`;
}

const statusColor: Record<string, string> = {
  pending: "default",
  running: "blue",
  completed: "green",
  failed: "red",
  cancelled: "default",
};

type Props = {
  open: boolean;
  onClose: () => void;
  onCompleted: () => void;
};

export default function CreateReportModal({ open, onClose, onCompleted }: Props) {
  const [dateFrom, setDateFrom] = useState<Dayjs>(todayMinus(7));
  const [dateTo, setDateTo] = useState<Dayjs>(todayMinus(0));
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [articles, setArticles] = useState<CrawledArticle[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/api/sources`)
      .then((res) => (res.ok ? res.json() : { sources: [] }))
      .then((data) => setSources(data.sources ?? []))
      .catch(() => setSources([]));
  }, []);

  function toggleSource(sourceId: string) {
    setSelectedSourceIds((prev) =>
      prev.includes(sourceId) ? prev.filter((id) => id !== sourceId) : [...prev, sourceId]
    );
  }

  function applyPreset(days: number) {
    setDateFrom(todayMinus(days));
    setDateTo(todayMinus(0));
  }

  const parsedDayCount = dateTo.diff(dateFrom, "day");
  const dayCount = Number.isFinite(parsedDayCount) ? Math.max(1, parsedDayCount) : 1;

  function updateStatus(data: JobStatus) {
    setStatus(data);
    if (!["pending", "running"].includes(data.status)) {
      sessionStorage.removeItem(JOB_ID_STORAGE_KEY);
      if (data.status === "completed") onCompleted();
    }
  }

  useEffect(() => {
    if (!open) return;
    const savedJobId = sessionStorage.getItem(JOB_ID_STORAGE_KEY);
    if (!savedJobId) return;
    (async () => {
      const [statusRes, articlesRes] = await Promise.all([
        fetch(`${API_BASE}/api/reports/${savedJobId}/status`),
        fetch(`${API_BASE}/api/reports/${savedJobId}/articles`),
      ]);
      if (!statusRes.ok) {
        sessionStorage.removeItem(JOB_ID_STORAGE_KEY);
        return;
      }
      setJobId(savedJobId);
      updateStatus(await statusRes.json());
      if (articlesRes.ok) setArticles((await articlesRes.json()).articles);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    const activeStatuses = ["pending", "running"];
    if (!jobId || !status || !activeStatuses.includes(status.status)) return;
    const interval = setInterval(async () => {
      const [statusRes, articlesRes] = await Promise.all([
        fetch(`${API_BASE}/api/reports/${jobId}/status`),
        fetch(`${API_BASE}/api/reports/${jobId}/articles`),
      ]);
      if (statusRes.ok) updateStatus(await statusRes.json());
      if (articlesRes.ok) setArticles((await articlesRes.json()).articles);
    }, 3000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, status?.status]);

  async function handleSubmit() {
    setError(null);
    const res = await fetch(`${API_BASE}/api/reports/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_ids: selectedSourceIds,
        date_from: dateFrom.format("YYYY-MM-DD"),
        date_to: dateTo.format("YYYY-MM-DD"),
      }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || "Tạo báo cáo thất bại");
      return;
    }
    const data = await res.json();
    sessionStorage.setItem(JOB_ID_STORAGE_KEY, data.job_id);
    setJobId(data.job_id);
    setArticles([]);
    updateStatus({ job_id: data.job_id, status: data.status, progress: { crawled: 0, analyzed: 0, total_estimated: 0 } });
  }

  async function handleCancel() {
    if (!status) return;
    const res = await fetch(`${API_BASE}/api/reports/${status.job_id}/cancel`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      updateStatus({ ...status, status: data.status });
    }
  }

  const disabled = !dateFrom || !dateTo || dateFrom.isAfter(dateTo) || selectedSourceIds.length === 0;
  const canCancel = status?.status === "pending" || status?.status === "running";
  const progressPercent = status && status.progress.total_estimated > 0
    ? Math.round(((status.progress.crawled + status.progress.analyzed) / (status.progress.total_estimated * 2)) * 100)
    : 0;

  return (
    <Modal open={open} onCancel={onClose} footer={null} width={800} title="Tạo báo cáo">
      <Space direction="vertical" style={{ width: "100%" }} size="middle">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <SourceSidebar sources={sources} selectedIds={selectedSourceIds} onToggle={toggleSource} />
          <div>
            <Space style={{ marginBottom: 8 }}>
              {DATE_PRESETS.map((preset) => (
                <Button key={preset.days} size="small" onClick={() => applyPreset(preset.days)}>
                  {preset.label}
                </Button>
              ))}
            </Space>
            <Space style={{ display: "flex", marginBottom: 12 }}>
              <div>
                <Typography.Text>Từ ngày</Typography.Text>
                <DatePicker value={dateFrom} onChange={(v) => v && setDateFrom(v)} style={{ display: "block" }} />
              </div>
              <div>
                <Typography.Text>Đến ngày</Typography.Text>
                <DatePicker value={dateTo} onChange={(v) => v && setDateTo(v)} style={{ display: "block" }} />
              </div>
            </Space>
            <SummaryCard sourceCount={selectedSourceIds.length} dayCount={dayCount} />
          </div>
        </div>

        <Button type="primary" disabled={disabled} onClick={handleSubmit}>
          Tạo báo cáo
        </Button>

        {error && <Alert type="error" message={error} showIcon />}

        {status && (
          <div>
            <Space align="center">
              <Tag color={statusColor[status.status]}>{status.status}</Tag>
              <Typography.Text>
                Đã crawl: {status.progress.crawled} bài — Đã phân tích: {status.progress.analyzed} bài
              </Typography.Text>
            </Space>
            <Progress percent={progressPercent} style={{ marginTop: 8 }} />
            <Space style={{ marginTop: 8 }}>
              {canCancel && (
                <Popconfirm title="Hủy job này?" onConfirm={handleCancel}>
                  <Button danger>Cancel</Button>
                </Popconfirm>
              )}
              {status.status === "completed" && (
                <Button type="link" href={`${API_BASE}/api/reports/${status.job_id}/download`}>
                  Tải báo cáo DOCX
                </Button>
              )}
            </Space>
            {status.status === "failed" && <Alert style={{ marginTop: 8 }} type="error" message={`Lỗi: ${status.error_log}`} />}
            {status.status === "cancelled" && <Alert style={{ marginTop: 8 }} type="info" message="Job đã bị hủy." />}
          </div>
        )}

        {articles.length > 0 && (
          <Table<CrawledArticle>
            size="small"
            rowKey="url"
            dataSource={articles}
            pagination={{ pageSize: 10 }}
            columns={[
              { title: "STT", render: (_v, _r, index) => index + 1, width: 60 },
              {
                title: "Tiêu đề",
                render: (_v, a) => (
                  <a href={a.url} target="_blank" rel="noopener noreferrer">
                    {a.title || a.url}
                  </a>
                ),
              },
              { title: "Nguồn", render: (_v, a) => a.source_name || "-" },
              { title: "Trạng thái", dataIndex: "status" },
              { title: "Crawl", render: (_v, a) => formatSeconds(a.crawl_duration_seconds) },
              { title: "Phân tích", render: (_v, a) => formatSeconds(a.analysis_duration_seconds) },
              { title: "Tổng", render: (_v, a) => formatSeconds(a.total_duration_seconds) },
            ]}
          />
        )}
      </Space>
    </Modal>
  );
}
```

- [ ] **Step 2: Cài `dayjs` (dependency của AntD DatePicker, thường đã có sẵn trong `antd`'s dependency graph nhưng cần khai báo trực tiếp để import)**

Run:
```bash
cd frontend
npm install dayjs
```

- [ ] **Step 3: Viết `ReportHistoryTable.tsx` — port từ `app/history/page.tsx` cũ**

```tsx
"use client";

import { useEffect, useState } from "react";
import { Table, Tag, Button, Typography } from "antd";
import { API_BASE } from "@/lib/api";

type HistoryEntry = {
  report_id: string;
  job_id: string;
  file_path: string;
  created_at: string;
  date_from: string;
  date_to: string;
  job_status: string;
  source_names: string[];
};

export type ReportHistoryTableHandle = { reload: () => void };

export default function ReportHistoryTable({ reloadToken }: { reloadToken: number }) {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/reports/history`)
      .then((res) => (res.ok ? res.json() : { history: [] }))
      .then((data) => setHistory(data.history ?? []))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));
  }, [reloadToken]);

  return (
    <Table<HistoryEntry>
      loading={loading}
      rowKey="report_id"
      dataSource={history}
      locale={{ emptyText: "Chưa có báo cáo nào." }}
      columns={[
        {
          title: "Ngày tạo",
          dataIndex: "created_at",
          render: (v: string) => new Date(v).toLocaleString("vi-VN"),
        },
        { title: "Nguồn", render: (_v, e) => e.source_names.join(", ") || "-" },
        { title: "Khoảng thời gian", render: (_v, e) => `${e.date_from} → ${e.date_to}` },
        {
          title: "Trạng thái",
          dataIndex: "job_status",
          render: (s: string) => <Tag color={s === "completed" ? "green" : "default"}>{s}</Tag>,
        },
        {
          title: "Tải về",
          render: (_v, e) => (
            <Button type="link" href={`${API_BASE}/api/reports/${e.job_id}/download`}>
              Tải DOCX
            </Button>
          ),
        },
      ]}
    />
  );
}
```

- [ ] **Step 4: Trang `/reports` gộp cả 2**

Tạo `frontend/app/(shell)/reports/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Button, Card, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import CreateReportModal from "@/components/reports/CreateReportModal";
import ReportHistoryTable from "@/components/reports/ReportHistoryTable";

export default function ReportsPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  return (
    <div>
      <Typography.Title level={3}>Báo cáo</Typography.Title>
      <Card
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            Tạo báo cáo
          </Button>
        }
      >
        <ReportHistoryTable reloadToken={reloadToken} />
      </Card>
      <CreateReportModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCompleted={() => setReloadToken((t) => t + 1)}
      />
    </div>
  );
}
```

- [ ] **Step 5: Xoá file cũ**

```bash
cd frontend
rm app/history/page.tsx
rmdir app/history 2>/dev/null || true
```

- [ ] **Step 6: Verify type**

Run: `cd frontend && npx tsc --noEmit`
Expected: không lỗi type.

- [ ] **Step 7: Verify với job thật (bắt buộc trước khi coi task này xong)**

1. Đảm bảo backend + Celery worker + Redis + Postgres + Ollama đang chạy (`docker compose up` theo README dự án).
2. `cd frontend && npm run dev`, mở `http://localhost:3000/reports`.
3. Bấm "Tạo báo cáo" → chọn nguồn VTV → chọn preset "7 ngày" → bấm "Tạo báo cáo" trong modal.
4. Xác nhận: modal hiển thị đúng trạng thái `pending`→`running`→`completed`, bảng crawl trực tiếp cập nhật mỗi 3 giây, nút Cancel hiện đúng lúc `pending`/`running` và biến mất khi `completed`.
5. Khi `completed`, đóng modal, xác nhận bảng lịch sử ở trang `/reports` tự động có thêm dòng mới (nhờ `onCompleted` → `reloadToken`).
6. Bấm "Tải DOCX" ở dòng vừa tạo, xác nhận file `.docx` tải về hợp lệ (mở được, có nội dung).
7. F5 lại trang trong lúc 1 job khác đang `running`, xác nhận modal tự khôi phục đúng job đang theo dõi khi mở lại (giữ hành vi `sessionStorage` cũ).

Expected: toàn bộ 6 bước trên chạy đúng như hành vi cũ (không có bước nào regress so với `app/page.tsx` + `app/history/page.tsx` trước khi refactor).

- [ ] **Step 8: Commit**

```bash
git add frontend/components/reports frontend/app/\(shell\)/reports frontend/package.json frontend/package-lock.json
git rm frontend/app/history/page.tsx
git commit -m "feat: gộp Tạo báo cáo + Lịch sử vào tab Báo cáo, viết lại bằng Ant Design"
```

---

## Task 9: Dọn dẹp cuối + verify toàn app

**Files:** không tạo file mới, chỉ verify.

- [ ] **Step 1: Xác nhận không còn tham chiếu file/route đã xoá**

Run:
```bash
cd frontend
grep -rn "components/SourceSidebar\"" app components 2>/dev/null
grep -rn "components/SummaryCard\"" app components 2>/dev/null
grep -rn "/history" app components 2>/dev/null
```

Expected: không có kết quả nào (ngoại trừ chính route `/system/audit-logs` nếu vô tình trùng chuỗi — kiểm tra thủ công nếu có match).

- [ ] **Step 2: Build production**

Run: `cd frontend && npm run build`
Expected: build thành công, không lỗi TypeScript/ESLint chặn build, liệt kê đủ các route: `/dashboard`, `/campaigns`, `/sources`, `/contents`, `/alerts`, `/cases`, `/reports`, `/jobs`, `/system`, `/system/master-data`, `/system/users`, `/system/audit-logs`, `/system/alert-rules`, `/system/crawler-settings`, `/system/report-settings`, `/system/settings`.

- [ ] **Step 3: Duyệt thủ công toàn bộ sidebar**

Chạy `npm run dev`, click lần lượt từng menu item trong sidebar (bao gồm mở submenu "Cấu hình hệ thống"), xác nhận:
- Menu item đang active được highlight đúng theo route hiện tại.
- Mỗi trang mock hiển thị đúng bố cục thẻ thống kê + bảng, không lỗi console.
- Trang `/sources` và `/reports` vẫn hoạt động thật như đã verify ở Task 6/8.

- [ ] **Step 4: Commit cuối (nếu có thay đổi phát sinh khi dọn dẹp)**

```bash
git add -A
git commit -m "chore: dọn dẹp cuối sau khi hoàn thành UI shell Ant Design"
```

(Bỏ qua bước này nếu không có thay đổi nào phát sinh.)

---

## Self-review

- **Spec coverage:** đủ shell (Task 2), 9 trang mock (Task 3–5), 2 trang thật Nguồn dữ liệu + Báo cáo (Task 6, 8), theme màu đúng ảnh (Task 1), redirect `/` → `/dashboard` (Task 2), xoá file cũ đúng kế hoạch (Task 7, 8).
- **Placeholder scan:** không còn "TBD"/"implement later" — mọi trang mock có dữ liệu mẫu cụ thể, mọi bước có lệnh/code đầy đủ.
- **Type consistency:** `SourceItem` dùng chung 1 định nghĩa duy nhất trong `components/reports/SourceSidebar.tsx`, được import lại ở `CreateReportModal.tsx` — không định nghĩa trùng. `API_BASE` chỉ định nghĩa 1 nơi (`lib/api.ts`), mọi file dùng API thật đều import từ đây.
- **Phạm vi:** đúng những gì đã chốt khi brainstorm — không Login, không tab con trong Cấu hình hệ thống, không sửa backend, không nối `jobs` table thật.

---

**Kế hoạch đã lưu tại `docs/superpowers/plans/2026-07-14-ngs-monitor-ui-shell-antd.md`.**
