# Vite + React UI Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thay thế toàn bộ frontend Next.js hiện tại bằng Vite + React, port nguyên UI từ `ngs-monitoring-ui/frontend/` (bố cục, màu sắc, mock data), giữ **thật** 2 tính năng đã review (Nguồn dữ liệu, Báo cáo), bỏ hẳn Auth, và chuyển Docker sang build tĩnh + nginx.

**Architecture:** Nhánh mới `feature/vite-ui-migration` tách từ `main`. Xoá nội dung cũ trong `frontend/`, dựng lại bằng Vite + React Router + AntD (giữ nguyên version AntD hiện có của repo, **không** hạ xuống v5 như code gốc của `ngs-monitoring-ui`). Bỏ `@tanstack/react-query`, `zustand`, `msw`, toàn bộ Auth — dùng `fetch` + `useState`/`useEffect` thuần xuyên suốt, khớp quy ước đã có ở phần Sources/Reports.

**Tech Stack:** Vite 5 + React 18 + TypeScript + React Router 6 + Ant Design (version hiện có trong `frontend/package.json` gốc — kiểm tra ở Task 1) + `@ant-design/icons` + `recharts` + `dayjs`. Docker: multi-stage build (Node build → nginx alpine serve static).

**Về kiểm thử:** Không có test suite tự động cho phần frontend (dự án `ngs-monitoring-ui` có Vitest nhưng ta không port theo, giữ đúng convention hiện tại của repo — không test tự động). Verify bằng `npm run build` + `tsc --noEmit` + kiểm tra thủ công qua trình duyệt/Playwright script + **bắt buộc 1 job thật** cho tab Báo cáo (giống các lần trước).

**Lưu ý quan trọng về phạm vi code trong plan này:** Với các trang **mock thuần** (Campaigns, Contents, Alerts, Cases, Jobs, System/*), thay vì chép lại hàng nghìn dòng code gốc vào plan này (rủi ro sai sót khi gõ lại thủ công), mỗi task sẽ nêu rõ **đường dẫn file nguồn thật đã tồn tại** trong `ngs-monitoring-ui/frontend/src/` và một **quy trình chuyển đổi cơ học, chính xác từng bước** (không phải mô tả mơ hồ) để người thực thi tự đọc file gốc rồi áp dụng đúng danh sách sửa đổi. Với các phần rủi ro cao/kiến trúc cốt lõi (scaffold, layout, routing, Sources, Reports, Docker), code đầy đủ được viết thẳng trong plan.

**Riêng `System/Connectors`** (file gốc dài 1581 dòng — 1 trình soạn cấu hình proxy/connector rất chi tiết): **cố ý giảm phạm vi** khi port, chỉ giữ bảng danh sách connector (không port panel chỉnh sửa proxy/fallback chi tiết từng nguồn) — vì đây là trang mock thuần, không có backend thật đứng sau, port đủ 1581 dòng cho 1 trang trang trí là vi phạm nguyên tắc YAGNI của dự án.

---

## File Structure

```
frontend/                                  # Xoá sạch nội dung Next.js cũ, dựng lại bằng Vite
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── Dockerfile                             # multi-stage: build → nginx
├── nginx.frontend.conf
├── src/
│   ├── main.tsx
│   ├── App.tsx                            # routing, không còn PrivateRoute/PublicRoute
│   ├── index.css
│   ├── theme/
│   │   └── index.ts
│   ├── lib/
│   │   └── api.ts                         # API_BASE constant (giữ đúng pattern cũ)
│   ├── data/
│   │   └── mockData.ts                    # port nguyên mocks/data.ts, bỏ phần auth-only
│   ├── layouts/
│   │   └── MainLayout.tsx                 # port, bỏ auth/logout
│   ├── components/
│   │   └── common/
│   │       ├── PageHeader.tsx
│   │       ├── StatusTag.tsx
│   │       ├── SeverityTag.tsx
│   │       ├── EmptyState.tsx
│   │       └── LoadingState.tsx
│   └── pages/
│       ├── Dashboard/index.tsx
│       ├── Sources/index.tsx              # THẬT — GET /api/sources
│       ├── Reports/
│       │   ├── index.tsx                  # THẬT — GET /api/reports/history
│       │   ├── ReportCreate.tsx           # THẬT — luồng job đầy đủ
│       │   ├── SourceSidebar.tsx
│       │   └── SummaryCard.tsx
│       ├── Campaigns/{index,CampaignForm,CampaignDetail}.tsx
│       ├── Contents/{index,ContentDetail}.tsx
│       ├── Alerts/{index,AlertDetail}.tsx
│       ├── Cases/{index,CaseForm,CaseDetail}.tsx
│       ├── Jobs/index.tsx
│       └── System/
│           ├── Users/{index,UserForm,UserModal}.tsx
│           ├── Roles/index.tsx
│           ├── MasterData/index.tsx
│           ├── Settings/index.tsx
│           ├── AuditLogs/index.tsx
│           └── Connectors/index.tsx        # rút gọn — chỉ bảng danh sách
docker-compose.yml                          # sửa service frontend
```

**Không tạo:** `Login`, `Profile`, `layouts/AuthLayout.tsx`, `store/auth.ts`, `services/http.ts` (axios+JWT), bất kỳ `*.service.ts` nào gọi `@tanstack/react-query`.

---

## Task 1: Khởi tạo Git branch + scaffold Vite

**Files:**
- Create: nhánh `feature/vite-ui-migration` từ `main`
- Modify: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/index.html`
- Delete: toàn bộ file Next.js cũ trong `frontend/` (`next.config.js`, `next-env.d.ts`, `app/`, cấu trúc App Router)

- [ ] **Step 1: Tạo nhánh mới từ main**

```bash
cd "d:/Tài liệu học lập trình/NGS-AI-Monitoring"
git checkout main
git pull
git checkout -b feature/vite-ui-migration
```

- [ ] **Step 2: Kiểm tra version AntD hiện có (giữ nguyên, không hạ xuống v5)**

```bash
cat frontend/package.json | grep '"antd"'
```
Ghi lại version này để dùng lại ở Step 3 (không copy version `^5.15.0` từ `ngs-monitoring-ui/frontend/package.json`).

- [ ] **Step 3: Xoá cấu trúc Next.js cũ, giữ lại `frontend/Dockerfile` để sửa ở Task 14**

```bash
cd frontend
rm -rf app next.config.js next-env.d.ts tailwind.config.js postcss.config.js
rm -f package-lock.json
```

- [ ] **Step 4: Viết `frontend/package.json` mới**

```json
{
  "name": "ngs-monitor-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "@ant-design/icons": "^5.3.0",
    "antd": "PASTE_VERSION_FROM_STEP_2",
    "dayjs": "^1.11.10",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.22.3",
    "recharts": "^2.12.3"
  },
  "devDependencies": {
    "@types/react": "^18.3.1",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.2.1",
    "typescript": "^5.4.2",
    "vite": "^5.2.6"
  }
}
```
Thay `PASTE_VERSION_FROM_STEP_2` bằng giá trị thật đọc được ở Step 2.

- [ ] **Step 5: Viết `frontend/vite.config.ts`**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
  },
});
```

- [ ] **Step 6: Viết `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 7: Viết `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 8: Viết `frontend/index.html`**

```html
<!doctype html>
<html lang="vi">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>NGS Monitor</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 9: Install dependencies**

```bash
cd frontend
npm install
```

- [ ] **Step 10: Verify**

Run: `cd frontend && npx tsc --noEmit`
Expected: lỗi "Cannot find module './App'" hoặc tương tự (chưa tạo `src/main.tsx`/`App.tsx`) — bình thường, sẽ hết ở Task 2.

- [ ] **Step 11: Commit**

```bash
git add frontend/package.json frontend/vite.config.ts frontend/tsconfig.json frontend/tsconfig.node.json frontend/index.html
git rm -r --cached frontend/app frontend/next.config.js frontend/next-env.d.ts frontend/tailwind.config.js frontend/postcss.config.js 2>/dev/null || true
git commit -m "chore: khởi tạo scaffold Vite thay cho Next.js"
```

---

## Task 2: main.tsx, theme, routing skeleton, MainLayout

**Files:**
- Create: `frontend/src/main.tsx`, `frontend/src/index.css`, `frontend/src/App.tsx`, `frontend/src/theme/index.ts`, `frontend/src/lib/api.ts`, `frontend/src/layouts/MainLayout.tsx`

- [ ] **Step 1: `frontend/src/lib/api.ts`**

```ts
export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
```

- [ ] **Step 2: `frontend/src/index.css`** — port nguyên từ `ngs-monitoring-ui/frontend/src/index.css` (đọc file đó, copy y nguyên nội dung — thuần CSS, không phụ thuộc React Query/Auth nên không cần sửa gì).

- [ ] **Step 3: `frontend/src/theme/index.ts`** — port nguyên từ `ngs-monitoring-ui/frontend/src/theme/index.ts` (đọc file đó, copy y nguyên — thuần AntD `ThemeConfig`, không phụ thuộc gì cần bỏ). Giữ đúng màu `BRAND`/`COLORS` gốc của họ (navy `#0B2262`, teal `#00859A`...) theo đúng quyết định "bê nguyên bố cục + màu sắc".

- [ ] **Step 4: `frontend/src/main.tsx`** — port từ `ngs-monitoring-ui/frontend/src/main.tsx`, bỏ phần react-query + MSW:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, App as AntdApp } from "antd";
import viVN from "antd/locale/vi_VN";
import dayjs from "dayjs";
import "dayjs/locale/vi";
import App from "./App";
import { theme } from "./theme";
import "./index.css";

dayjs.locale("vi");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ConfigProvider theme={theme} locale={viVN}>
        <AntdApp>
          <App />
        </AntdApp>
      </ConfigProvider>
    </BrowserRouter>
  </React.StrictMode>
);
```

- [ ] **Step 5: `frontend/src/App.tsx`** — port từ `ngs-monitoring-ui/frontend/src/App.tsx`, bỏ `PrivateRoute`/`PublicRoute`/`AuthLayout`/Login/Profile, đổi 2 route Reports theo quyết định đã chốt (`/reports/create` không phải `/reports/new`), đổi route System theo cấu trúc gốc của họ (giữ `roles`, `master-data`, `settings`, `audit-logs`, `connectors` — đúng như code gốc, KHÔNG theo ảnh mẫu phẳng):

```tsx
import { Navigate, Route, Routes } from "react-router-dom";
import MainLayout from "@/layouts/MainLayout";
import DashboardPage from "@/pages/Dashboard";
import CampaignsPage from "@/pages/Campaigns";
import CampaignForm from "@/pages/Campaigns/CampaignForm";
import CampaignDetail from "@/pages/Campaigns/CampaignDetail";
import SourcesPage from "@/pages/Sources";
import ContentsPage from "@/pages/Contents";
import ContentDetail from "@/pages/Contents/ContentDetail";
import AlertsPage from "@/pages/Alerts";
import AlertDetail from "@/pages/Alerts/AlertDetail";
import CasesPage from "@/pages/Cases";
import CaseForm from "@/pages/Cases/CaseForm";
import CaseDetail from "@/pages/Cases/CaseDetail";
import ReportsPage from "@/pages/Reports";
import ReportCreate from "@/pages/Reports/ReportCreate";
import JobsPage from "@/pages/Jobs";
import UsersPage from "@/pages/System/Users";
import UserForm from "@/pages/System/Users/UserForm";
import RolesPage from "@/pages/System/Roles";
import MasterDataPage from "@/pages/System/MasterData";
import SystemSettings from "@/pages/System/Settings";
import AuditLogsPage from "@/pages/System/AuditLogs";
import ConnectorsPage from "@/pages/System/Connectors";

export default function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route path="/" element={<DashboardPage />} />

        <Route path="/campaigns" element={<CampaignsPage />} />
        <Route path="/campaigns/new" element={<CampaignForm />} />
        <Route path="/campaigns/:id" element={<CampaignDetail />} />
        <Route path="/campaigns/:id/edit" element={<CampaignForm />} />

        <Route path="/sources" element={<SourcesPage />} />

        <Route path="/contents" element={<ContentsPage />} />
        <Route path="/contents/:id" element={<ContentDetail />} />

        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/alerts/:id" element={<AlertDetail />} />

        <Route path="/cases" element={<CasesPage />} />
        <Route path="/cases/new" element={<CaseForm />} />
        <Route path="/cases/:id" element={<CaseDetail />} />
        <Route path="/cases/:id/edit" element={<CaseForm />} />

        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/reports/create" element={<ReportCreate />} />

        <Route path="/jobs" element={<JobsPage />} />

        <Route path="/system/users" element={<UsersPage />} />
        <Route path="/system/users/new" element={<UserForm />} />
        <Route path="/system/users/:id/edit" element={<UserForm />} />
        <Route path="/system/roles" element={<RolesPage />} />
        <Route path="/system/master-data" element={<MasterDataPage />} />
        <Route path="/system/settings" element={<SystemSettings />} />
        <Route path="/system/audit-logs" element={<AuditLogsPage />} />
        <Route path="/system/connectors" element={<ConnectorsPage />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
```

**Lưu ý:** không có `Route path="/sources/new"`/`"/sources/:id/edit"` — vì `SourceForm.tsx` không được port (Sources chỉ đọc thật, không có CRUD, giữ đúng quyết định của bản Next.js).

- [ ] **Step 6: `frontend/src/layouts/MainLayout.tsx`** — port từ `ngs-monitoring-ui/frontend/src/layouts/MainLayout.tsx`, bỏ toàn bộ phần auth/logout, sửa `/logo.svg` (không tồn tại file thật) thành chữ "NGS" thuần:

```tsx
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

  const openKeys = MENU_ITEMS.filter(
    (m) => m.children?.some((c) => (c.children ? c.children.some((cc) => location.pathname.startsWith(cc.key)) : location.pathname.startsWith(c.key)))
  ).map((m) => m.key);

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
            justifyContent: collapsed ? "center" : "flex-start",
            padding: collapsed ? 0 : "0 18px",
            borderBottom: "1px solid rgba(255,255,255,0.1)",
            background: "rgba(0,0,0,0.15)",
            flexShrink: 0,
          }}
        >
          {!collapsed ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
              <Typography.Text style={{ color: "#fff", fontWeight: 800, fontSize: 22, lineHeight: 1 }}>NGS</Typography.Text>
              <Typography.Text style={{ color: "rgba(255,255,255,0.55)", fontSize: 10, letterSpacing: 0.5, marginTop: 2 }}>
                Monitor Platform
              </Typography.Text>
            </div>
          ) : (
            <Typography.Text style={{ color: "#fff", fontWeight: 800, fontSize: 18 }}>N</Typography.Text>
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
```

**Khác biệt so với code gốc:** bỏ `useAuthStore`/`authService`/`doLogout`/`userMenuItems`/`Dropdown` (không có logout thật), bỏ `KeyOutlined`/`LogoutOutlined`, avatar không còn dropdown — chỉ hiển thị tên tĩnh "Nguyễn Văn A", logo thay `<img src="/logo.svg">` (file không tồn tại trong project gốc) bằng chữ "NGS" dạng text.

- [ ] **Step 7: Verify**

Run: `cd frontend && npx tsc --noEmit`
Expected: lỗi thiếu module cho các trang chưa tạo (`@/pages/Dashboard`, `@/pages/Sources`...) — bình thường, sẽ hết dần qua các task sau.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/main.tsx frontend/src/index.css frontend/src/App.tsx frontend/src/theme frontend/src/lib frontend/src/layouts
git commit -m "feat: dựng routing + MainLayout + theme cho Vite app"
```

---

## Task 3: Common components + mock data file

**Files:**
- Create: `frontend/src/components/common/{PageHeader,StatusTag,SeverityTag,EmptyState,LoadingState}.tsx`
- Create: `frontend/src/data/mockData.ts`

- [ ] **Step 1-5: Copy 5 component thuần, không sửa gì**

Đọc trực tiếp và copy y nguyên nội dung từ:
- `ngs-monitoring-ui/frontend/src/components/common/PageHeader.tsx` → `frontend/src/components/common/PageHeader.tsx`
- `ngs-monitoring-ui/frontend/src/components/common/StatusTag.tsx` → `frontend/src/components/common/StatusTag.tsx`
- `ngs-monitoring-ui/frontend/src/components/common/SeverityTag.tsx` → `frontend/src/components/common/SeverityTag.tsx`
- `ngs-monitoring-ui/frontend/src/components/common/EmptyState.tsx` → `frontend/src/components/common/EmptyState.tsx`
- `ngs-monitoring-ui/frontend/src/components/common/LoadingState.tsx` → `frontend/src/components/common/LoadingState.tsx`

5 file này không import gì từ service/auth/react-query — copy nguyên xi, không cần sửa.

- [ ] **Step 6: Port mock data**

Đọc `ngs-monitoring-ui/frontend/src/mocks/data.ts`, copy sang `frontend/src/data/mockData.ts`, **bỏ** 2 export sau (chỉ dùng cho auth, không cần):
```ts
export const DEMO_TOKEN = ...
export const DEMO_REFRESH = ...
```
Giữ nguyên toàn bộ phần còn lại (`DEMO_USER`, `platforms`, `sourceCategories`, `sources`, `roles`, `users`, `campaigns`, `surveyDetail`, `contents`, `alerts`, `cases`, `reports`, `auditLogs`, `jobs`, `permissions`, `connectors`, `connectorSources`, hàm `paginate`) — đây là data mẫu chất lượng cao (tiếng Việt, đúng ngữ cảnh NGS Monitor), dùng cho toàn bộ các trang mock ở Task 7-13.

- [ ] **Step 7: Verify**

Run: `cd frontend && npx tsc --noEmit`
Expected: không lỗi ở 6 file mới này (có thể vẫn còn lỗi thiếu trang khác, bỏ qua).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/common frontend/src/data
git commit -m "feat: copy common components + mock data từ ngs-monitoring-ui"
```

---

## Task 4: Dashboard (port nguyên, không cần sửa data layer)

**Files:**
- Create: `frontend/src/pages/Dashboard/index.tsx`

- [ ] **Step 1: Port nguyên xi**

Đọc `ngs-monitoring-ui/frontend/src/pages/Dashboard/index.tsx` (225 dòng), copy y nguyên sang `frontend/src/pages/Dashboard/index.tsx` — **không cần sửa import hay logic nào**, vì file này không gọi `useQuery`/service nào cả, toàn bộ data (`trendData`, `sentimentData`, `platformData`, `keywordsData`, `recentAlerts`, `kpiCards`) đã là hằng số khai báo ngay trong file. Chỉ cần đổi import `COLORS` từ `@/theme` (đã có ở Task 2) và `SeverityTag`/`StatusTag`/`PageHeader` từ `@/components/common/*` (đã có ở Task 3) — 2 import path này giữ nguyên vì đúng cấu trúc thư mục đã dựng.

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc --noEmit`
Expected: hết lỗi liên quan `@/pages/Dashboard`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Dashboard
git commit -m "feat: port trang Dashboard nguyên bản từ ngs-monitoring-ui"
```

---

## Task 5: Sources (thật — GET /api/sources)

**Files:**
- Create: `frontend/src/pages/Sources/index.tsx`

- [ ] **Step 1: Viết trang Sources — port bố cục UI của họ, thay toàn bộ data layer bằng fetch thật**

```tsx
import { useEffect, useState } from "react";
import { Button, Card, Input, Space, Table, Tag, Tooltip, Typography } from "antd";
import { SearchOutlined, EditOutlined, ApiOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import { API_BASE } from "@/lib/api";

type Source = {
  source_id: string;
  name: string;
  domain: string;
  group_name: string;
};

export default function SourcesPage() {
  const navigate = useNavigate();
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/api/sources`)
      .then((res) => (res.ok ? res.json() : { sources: [] }))
      .then((data) => {
        setSources(data.sources ?? []);
        setError(null);
      })
      .catch(() => setError("Không tải được danh sách nguồn dữ liệu"))
      .finally(() => setLoading(false));
  }, []);

  const filtered = sources.filter((s) => s.name.toLowerCase().includes(keyword.toLowerCase()));

  const columns = [
    { title: "Tên nguồn", dataIndex: "name", key: "name", render: (v: string) => <span style={{ fontWeight: 500 }}>{v}</span> },
    { title: "Nhóm nguồn", dataIndex: "group_name", key: "group_name" },
    { title: "Domain", dataIndex: "domain", key: "domain" },
    {
      title: "Trạng thái",
      key: "status",
      render: () => <Tag color="success">Đang hoạt động</Tag>,
    },
    {
      title: "Thao tác",
      key: "actions",
      width: 140,
      render: (_: unknown, r: Source) => (
        <Space>
          <Tooltip title="Chưa triển khai — CRUD nguồn qua UI thuộc phạm vi Slice 6, chưa code">
            <Button type="text" icon={<ApiOutlined />} disabled />
          </Tooltip>
          <Tooltip title="Chưa triển khai">
            <Button type="text" icon={<EditOutlined />} disabled />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Nguồn dữ liệu"
        subtitle="Danh sách nguồn thu thập thông tin"
        breadcrumbs={[{ title: "Tổng quan", href: "/" }, { title: "Nguồn dữ liệu" }]}
      />

      {error && (
        <Typography.Text type="danger" style={{ display: "block", marginBottom: 16 }}>
          {error}
        </Typography.Text>
      )}

      <Card style={{ borderRadius: 12 }}>
        <Space style={{ marginBottom: 16 }}>
          <Input
            placeholder="Tìm kiếm nguồn..."
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 280 }}
            allowClear
          />
        </Space>

        <Table
          columns={columns}
          dataSource={filtered}
          rowKey="source_id"
          loading={loading}
          pagination={{ pageSize: 20, showTotal: (t) => `Tổng ${t} nguồn` }}
        />
      </Card>
    </div>
  );
}
```

**Khác biệt so với code gốc của họ:** bỏ `useQuery`/`campaignService`-style `sourceService`, bỏ phân trang server-side (`page`/`page_size` params — backend không hỗ trợ), bỏ filter theo `status` (backend không trả field này), bỏ nút "Thêm nguồn"/`ConfirmDeleteModal`/`PermissionGuard` (CRUD chưa có), cột "Trạng thái" luôn hiện "Đang hoạt động" (giữ đúng logic đã review ở bản Next.js — backend `GET /api/sources` chỉ trả nguồn active, không có field `is_active` trong response), có `Alert`/`Typography.Text type="danger"` báo lỗi khi fetch thất bại (giữ đúng fix đã review).

- [ ] **Step 2: Verify với backend thật**

Run: `cd frontend && npm run dev`, mở `http://localhost:3000/sources` (đảm bảo backend đang chạy ở `:8000`).
Expected: bảng hiển thị đúng 7 nguồn thật (VTV, VOV, VietnamPlus, CAND, BoCongAn, TinGia, Vietnam.vn), nút hành động bị mờ kèm tooltip.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Sources
git commit -m "feat: port trang Nguồn dữ liệu, nối thật GET /api/sources"
```

---

## Task 6: Reports (thật — 2 trang, luồng job đầy đủ)

**Files:**
- Create: `frontend/src/pages/Reports/SourceSidebar.tsx`
- Create: `frontend/src/pages/Reports/SummaryCard.tsx`
- Create: `frontend/src/pages/Reports/index.tsx`
- Create: `frontend/src/pages/Reports/ReportCreate.tsx`

- [ ] **Step 1: Port `SourceSidebar.tsx` — copy nguyên xi từ bản Next.js đã review**

Đọc `frontend`(Next.js cũ, trước khi bị xoá ở Task 1 — **đọc từ git history**: `git show main:frontend/... ` không còn vì đây là nhánh mới từ main không có bản AntD. **Dùng nội dung dưới đây trực tiếp**, đã lấy nguyên từ bản đã review kỹ ở nhánh `feature/slice-6-build-ui`):

```tsx
import { useMemo, useState } from "react";
import { Input, Checkbox, Tag, Typography } from "antd";
import { SearchOutlined, CloseOutlined } from "@ant-design/icons";

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
            <Tag
              key={s.source_id}
              closable
              onClose={() => onToggle(s.source_id)}
              color="blue"
              closeIcon={<CloseOutlined aria-label={`Bỏ chọn ${s.name}`} />}
            >
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

- [ ] **Step 2: Port `SummaryCard.tsx` — copy nguyên xi**

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

- [ ] **Step 3: Viết `frontend/src/pages/Reports/index.tsx`** — port style Card/Table/PageHeader từ `ngs-monitoring-ui/frontend/src/pages/Reports/index.tsx`, thay data layer bằng logic đã review của `ReportHistoryTable.tsx` (Next.js):

```tsx
import { useEffect, useState } from "react";
import { Button, Card, Table, Tag } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
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

export default function ReportsPage() {
  const navigate = useNavigate();
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/reports/history`)
      .then((res) => (res.ok ? res.json() : { history: [] }))
      .then((data) => setHistory(data.history ?? []))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <PageHeader
        title="Báo cáo"
        subtitle="Xem và tải báo cáo giám sát"
        breadcrumbs={[{ title: "Tổng quan", href: "/" }, { title: "Báo cáo" }]}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/reports/create")}>
            Tạo báo cáo
          </Button>
        }
      />

      <Card style={{ borderRadius: 12 }}>
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
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  );
}
```

**Lưu ý:** trang này không tự động refresh khi 1 job khác vừa hoàn thành (khác bản Next.js dùng `reloadToken` prop giữa 2 component cùng 1 trang) — vì giờ đây `ReportCreate` là 1 trang riêng, không phải modal cùng trang. Người dùng quay lại `/reports` (qua nút "Hủy" hoặc điều hướng) sẽ thấy `useEffect` chạy lại và tự fetch danh sách mới nhất — **hành vi tương đương, chỉ khác cơ chế trigger** (điều hướng trang thay vì state callback).

- [ ] **Step 4: Viết `frontend/src/pages/Reports/ReportCreate.tsx`** — port khung `PageHeader`/`Card` từ file gốc của họ, thay **toàn bộ** nội dung form bằng logic đã review của `CreateReportModal.tsx` (Next.js), bỏ lớp `Modal` (giờ là trang riêng, không phải modal), điều hướng bằng `useNavigate` sau khi hoàn tất:

```tsx
import { useEffect, useState } from "react";
import { Button, Card, DatePicker, Space, Table, Tag, Alert, Progress, Popconfirm, Typography } from "antd";
import dayjs, { Dayjs } from "dayjs";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
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

export default function ReportCreate() {
  const navigate = useNavigate();
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
    }
  }

  // Khôi phục job đang chạy sau F5 — trang này luôn mount ngay khi user vào /reports/create,
  // KHÔNG cần cơ chế "tự mở modal" như bản Next.js (vì đây đã là 1 trang riêng, luôn hiển thị).
  useEffect(() => {
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
  }, []);

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
    <div>
      <PageHeader
        title="Tạo báo cáo mới"
        breadcrumbs={[{ title: "Tổng quan", href: "/" }, { title: "Báo cáo", href: "/reports" }, { title: "Tạo mới" }]}
      />

      <Card style={{ borderRadius: 12 }}>
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

          <Space>
            <Button type="primary" disabled={disabled} onClick={handleSubmit}>
              Tạo báo cáo
            </Button>
            <Button onClick={() => navigate("/reports")}>Hủy</Button>
          </Space>

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
      </Card>
    </div>
  );
}
```

**Điểm khác biệt quan trọng so với bản Next.js (đã đơn giản hoá đúng hướng, không phải bug):** vì `ReportCreate` giờ là 1 trang riêng luôn mount khi truy cập `/reports/create`, cơ chế F5-recovery đơn giản hơn hẳn — không cần "tự mở modal" (vấn đề Critical đã gặp và sửa ở bản Next.js), chỉ cần `useEffect` rỗng deps chạy 1 lần lúc mount, y hệt cách hoạt động ban đầu trước khi bản Next.js chuyển sang cấu trúc modal.

- [ ] **Step 5: Verify type**

Run: `cd frontend && npx tsc --noEmit`
Expected: không lỗi.

- [ ] **Step 6: Verify với job thật (bắt buộc)**

1. Đảm bảo backend + Celery + Redis + Postgres + Ollama đang chạy đúng (kiểm tra `docker compose exec ollama ollama list` trả về đúng `qwen3:8b`, tránh lặp lại vấn đề đã gặp).
2. `npm run dev`, mở `/reports` → bấm "Tạo báo cáo" → chọn nguồn VTV, preset "7 ngày" → bấm "Tạo báo cáo".
3. Xác nhận: trạng thái `pending → running → completed`, bảng crawl cập nhật mỗi 3s, Cancel hiện đúng lúc, tải DOCX được khi `completed`.
4. Quay lại `/reports`, xác nhận báo cáo mới xuất hiện trong bảng lịch sử.
5. F5 giữa lúc job đang `running`, xác nhận `/reports/create` tự hiển thị lại đúng job đang theo dõi.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/Reports
git commit -m "feat: port tab Báo cáo — 2 trang, luồng job thật đầy đủ"
```

---

## Task 7: Campaigns (mock — 3 file, quy trình chuyển đổi mẫu)

**Files:**
- Create: `frontend/src/pages/Campaigns/index.tsx`
- Create: `frontend/src/pages/Campaigns/CampaignForm.tsx`
- Create: `frontend/src/pages/Campaigns/CampaignDetail.tsx`

**Đây là task mẫu cho quy trình "port trang mock" — áp dụng lại đúng quy trình 7 bước dưới đây cho Task 8-13.**

- [ ] **Step 1: Đọc file nguồn**

Đọc `ngs-monitoring-ui/frontend/src/pages/Campaigns/index.tsx`.

- [ ] **Step 2: Áp dụng checklist chuyển đổi (áp dụng cho MỌI trang mock từ đây về sau)**

1. Xoá `import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'`.
2. Xoá `import { campaignService } from '@/services/campaign.service'` (hoặc service tương ứng) — không tạo file `services/*.ts` nào cả trong dự án này.
3. Xoá `import PermissionGuard from '@/components/common/PermissionGuard'` — xoá luôn mọi cặp thẻ `<PermissionGuard permission="...">...</PermissionGuard>` bọc quanh nút, **giữ lại phần con bên trong** (không bọc gì cả — mọi nút đều hiển thị, vì không có RBAC thật).
4. Thay khối `const { data, isLoading } = useQuery({...})` bằng:
   ```ts
   import { campaigns as mockCampaigns } from "@/data/mockData";
   const [data] = useState(mockCampaigns);
   const isLoading = false;
   ```
5. Xoá khối `const { mutate: deleteCampaign, isPending: deleting } = useMutation({...})` và mọi nút/hành động gọi nó (nút xoá) — **giữ nguyên** `ConfirmDeleteModal` nếu import cho mục đích hiển thị được (có thể xoá state `deleteId` liên quan nếu không còn dùng ở đâu khác) — **hoặc** đơn giản nhất: xoá cả cụm nút Xoá + `ConfirmDeleteModal` khỏi trang (vì không có backend để xoá thật, hiện nút xoá không hoạt động dễ gây hiểu lầm — nhất quán với quyết định "Sources không có nút Xoá hoạt động").
6. Đổi `pagination={{ current: page, pageSize: 20, total: data?.total ?? 0, onChange: setPage, showTotal: ... }}` (server-side) thành `pagination={{ pageSize: 20, showTotal: (t) => \`Tổng ${t} chiến dịch\` }}` (client-side, vì `mockCampaigns` là mảng tĩnh đầy đủ, không cần gọi lại server khi đổi trang).
7. Giữ nguyên toàn bộ: `columns`, `StatusTag`, `PageHeader`, filter `Input`/`Select` (search/status vẫn lọc được vì chạy trên mảng tĩnh phía client — sửa `dataSource={data}` thành `dataSource={data.filter(c => (!keyword || c.name.toLowerCase().includes(keyword.toLowerCase())) && (!status || c.status === status))}`), `dayjs` formatting, `navigate(...)`.

- [ ] **Step 3: Viết file kết quả** `frontend/src/pages/Campaigns/index.tsx` theo đúng checklist trên.

- [ ] **Step 4: Port `CampaignForm.tsx` và `CampaignDetail.tsx`**

Đọc `ngs-monitoring-ui/frontend/src/pages/Campaigns/CampaignForm.tsx` và `CampaignDetail.tsx`, áp dụng đúng checklist Step 2 (mục 1-3 áp dụng nguyên vẹn; mục 4 thay bằng đọc 1 phần tử tĩnh từ `mockCampaigns`/`surveyDetail` theo `id` param qua `useParams()`; mục 5 — `CampaignForm`'s `onFinish`/`mutate` khi submit chỉ hiện `message.info("Đây là giao diện minh hoạ — chưa lưu được thật")` rồi `navigate('/campaigns')`, không gọi API nào).

- [ ] **Step 5: Verify**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Campaigns
git commit -m "feat: port trang Chiến dịch giám sát (mock)"
```

---

## Task 8: Contents + Alerts (mock — áp dụng checklist Task 7)

**Files:**
- Create: `frontend/src/pages/Contents/index.tsx`, `frontend/src/pages/Contents/ContentDetail.tsx`
- Create: `frontend/src/pages/Alerts/index.tsx`, `frontend/src/pages/Alerts/AlertDetail.tsx`

- [ ] **Step 1:** Đọc `ngs-monitoring-ui/frontend/src/pages/Contents/index.tsx` + `ContentDetail.tsx`, áp dụng checklist Task 7 Step 2 (dùng `contents` từ `@/data/mockData`, dùng `SeverityTag`/`StatusTag` type="content"/"sentiment" tương ứng).
- [ ] **Step 2:** Đọc `ngs-monitoring-ui/frontend/src/pages/Alerts/index.tsx` + `AlertDetail.tsx`, áp dụng checklist Task 7 Step 2 (dùng `alerts` từ `@/data/mockData`).
- [ ] **Step 3: Verify** — `cd frontend && npx tsc --noEmit`
- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Contents frontend/src/pages/Alerts
git commit -m "feat: port trang Nội dung + Cảnh báo (mock)"
```

---

## Task 9: Cases (mock — áp dụng checklist Task 7)

**Files:**
- Create: `frontend/src/pages/Cases/index.tsx`, `frontend/src/pages/Cases/CaseForm.tsx`, `frontend/src/pages/Cases/CaseDetail.tsx`

- [ ] **Step 1:** Đọc 3 file gốc trong `ngs-monitoring-ui/frontend/src/pages/Cases/`, áp dụng checklist Task 7 Step 2 (dùng `cases` từ `@/data/mockData`).
- [ ] **Step 2: Verify** — `cd frontend && npx tsc --noEmit`
- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Cases
git commit -m "feat: port trang Vụ việc (mock)"
```

---

## Task 10: Jobs (mock — file đơn giản nhất, 64 dòng)

**Files:**
- Create: `frontend/src/pages/Jobs/index.tsx`

- [ ] **Step 1:** Đọc `ngs-monitoring-ui/frontend/src/pages/Jobs/index.tsx`, áp dụng checklist Task 7 Step 2 (dùng `jobs` từ `@/data/mockData`). **Lưu ý:** trang `/jobs` này là mock, khác với luồng job thật của Báo cáo (`/reports/create`) — không nối gì với `GET /api/reports/{id}/status` cả, giữ đúng quyết định "chỉ Sources + Reports là thật" đã chốt khi build bản Next.js.
- [ ] **Step 2: Verify** — `cd frontend && npx tsc --noEmit`
- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Jobs
git commit -m "feat: port trang Lịch chạy & Jobs (mock)"
```

---

## Task 11: System/Users + System/Roles (mock — áp dụng checklist Task 7)

**Files:**
- Create: `frontend/src/pages/System/Users/index.tsx`, `UserForm.tsx`, `UserModal.tsx`
- Create: `frontend/src/pages/System/Roles/index.tsx`

- [ ] **Step 1:** Đọc 3 file gốc trong `ngs-monitoring-ui/frontend/src/pages/System/Users/` (`index.tsx` 305 dòng, `UserForm.tsx` 225 dòng, `UserModal.tsx` 627 dòng — file lớn nhất nhóm này, chủ yếu là 1 modal xem chi tiết user nhiều tab, port nguyên cấu trúc tab nhưng data lấy tĩnh từ `users` trong `@/data/mockData`), áp dụng checklist Task 7 Step 2.
- [ ] **Step 2:** Đọc `ngs-monitoring-ui/frontend/src/pages/System/Roles/index.tsx` (367 dòng), áp dụng checklist Task 7 Step 2 (dùng `roles` từ `@/data/mockData`).
- [ ] **Step 3: Verify** — `cd frontend && npx tsc --noEmit`
- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/System/Users frontend/src/pages/System/Roles
git commit -m "feat: port trang Người dùng & Nhóm quyền (mock)"
```

---

## Task 12: System/MasterData + System/Settings + System/AuditLogs (mock)

**Files:**
- Create: `frontend/src/pages/System/MasterData/index.tsx`
- Create: `frontend/src/pages/System/Settings/index.tsx`
- Create: `frontend/src/pages/System/AuditLogs/index.tsx`

- [ ] **Step 1:** Đọc `ngs-monitoring-ui/frontend/src/pages/System/MasterData/index.tsx` (426 dòng — nhiều tab: Nhóm nguồn/Nền tảng/Chủ đề/Từ khóa...), áp dụng checklist Task 7 Step 2 (dùng `platforms`/`sourceCategories` từ `@/data/mockData`, các tab không có data mẫu tương ứng thì để mảng rỗng + `EmptyState`).
- [ ] **Step 2:** Đọc `ngs-monitoring-ui/frontend/src/pages/System/Settings/index.tsx` (62 dòng, ngắn — khả năng chỉ là 1 Form tĩnh không gọi API), áp dụng checklist Task 7 Step 2 nếu có gọi service, nếu không thì copy gần như nguyên xi (chỉ xoá `PermissionGuard` nếu có).
- [ ] **Step 3:** Đọc `ngs-monitoring-ui/frontend/src/pages/System/AuditLogs/index.tsx` (84 dòng), áp dụng checklist Task 7 Step 2 (dùng `auditLogs` từ `@/data/mockData`).
- [ ] **Step 4: Verify** — `cd frontend && npx tsc --noEmit`
- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/System/MasterData frontend/src/pages/System/Settings frontend/src/pages/System/AuditLogs
git commit -m "feat: port trang Dữ liệu danh mục + Cài đặt + Nhật ký (mock)"
```

---

## Task 13: System/Connectors (mock — RÚT GỌN có chủ đích)

**Files:**
- Create: `frontend/src/pages/System/Connectors/index.tsx`

- [ ] **Step 1: Đọc file gốc nhưng CHỈ port phần bảng danh sách**

Đọc `ngs-monitoring-ui/frontend/src/pages/System/Connectors/index.tsx` (1581 dòng — file lớn nhất toàn bộ codebase tham khảo, chứa panel chỉnh sửa chi tiết proxy/fallback/retry cho từng connector). **Không port nguyên 1581 dòng** — chỉ lấy phần đầu file dựng bảng danh sách connector (import, `PageHeader`, `Table` liệt kê `connectors` từ mock data với cột Platform/Method/Status/Success Rate), bỏ toàn bộ phần `Drawer`/panel chỉnh sửa proxy chi tiết từng nguồn (không cần thiết cho 1 trang trang trí không có backend thật đứng sau — vi phạm YAGNI nếu port đủ).

- [ ] **Step 2: Viết bảng đơn giản**

```tsx
import { Card, Table, Tag, Typography } from "antd";
import PageHeader from "@/components/common/PageHeader";
import { connectors } from "@/data/mockData";

const STATUS_COLOR: Record<string, string> = {
  ACTIVE: "success",
  WARNING: "warning",
  PAUSED: "default",
};

export default function ConnectorsPage() {
  return (
    <div>
      <PageHeader
        title="Cấu hình Connector"
        subtitle="Trạng thái kết nối thu thập dữ liệu theo từng nền tảng"
        breadcrumbs={[{ title: "Tổng quan", href: "/" }, { title: "Cấu hình hệ thống" }, { title: "Cấu hình Connector" }]}
      />
      <Typography.Paragraph type="secondary">
        Trang này chỉ minh hoạ giao diện — chưa có chức năng chỉnh sửa cấu hình proxy/fallback thật.
      </Typography.Paragraph>
      <Card style={{ borderRadius: 12 }}>
        <Table
          rowKey="id"
          dataSource={connectors}
          pagination={false}
          columns={[
            { title: "Nền tảng", dataIndex: "platform" },
            { title: "Tên Connector", dataIndex: "name" },
            { title: "Phương thức", dataIndex: "method" },
            {
              title: "Trạng thái",
              dataIndex: "status",
              render: (v: string) => <Tag color={STATUS_COLOR[v] ?? "default"}>{v}</Tag>,
            },
            {
              title: "Tỷ lệ thành công",
              dataIndex: "success_rate",
              render: (v: number | null) => (v == null ? "—" : `${v}%`),
            },
            { title: "Kiểm tra lần cuối", dataIndex: "last_checked_at", render: (v: string) => new Date(v).toLocaleString("vi-VN") },
          ]}
        />
      </Card>
    </div>
  );
}
```

- [ ] **Step 3: Verify** — `cd frontend && npx tsc --noEmit`
- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/System/Connectors
git commit -m "feat: port trang Cấu hình Connector (mock, rút gọn — chỉ bảng danh sách)"
```

---

## Task 14: Docker — multi-stage build + nginx

**Files:**
- Modify: `frontend/Dockerfile`
- Create: `frontend/nginx.frontend.conf`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Viết `frontend/Dockerfile`**

```dockerfile
## Build stage
FROM node:20-alpine AS builder

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend .
RUN npm run build

## Production stage — static files served by nginx
FROM nginx:1.27-alpine AS production

COPY --from=builder /app/dist /usr/share/nginx/html
COPY frontend/nginx.frontend.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 2: Viết `frontend/nginx.frontend.conf`**

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    server_tokens off;

    location ~* \.(js|css|woff2?|ttf|eot|svg|ico|png|jpg|jpeg|gif|webp)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    location /health {
        access_log off;
        return 200 "OK\n";
        add_header Content-Type text/plain;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 3: Sửa service `frontend` trong `docker-compose.yml`**

Đọc `docker-compose.yml` hiện tại (service `frontend`, khoảng dòng 100-118), sửa thành:

```yaml
  frontend:
    build:
      context: .
      dockerfile: frontend/Dockerfile
    env_file: .env
    ports:
      - "3000:80"
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:80/health"]
      interval: 5s
      timeout: 5s
      retries: 10
```

**Khác biệt so với cấu hình cũ:** bỏ 3 dòng `volumes` (không cần mount source code vào container nữa — bản production đã build sẵn tĩnh, không hot-reload), cổng nội bộ container đổi từ `3000` (Next.js) sang `80` (nginx), map ra ngoài vẫn giữ `3000:80` để không đổi thói quen truy cập `localhost:3000`.

- [ ] **Step 4: Cập nhật biến môi trường**

Trong `.env.example`, đổi:
```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```
thành:
```env
VITE_API_BASE_URL=http://localhost:8000
```
(khớp `frontend/src/lib/api.ts` đã viết ở Task 2, dùng `import.meta.env.VITE_API_BASE_URL`). Nhắc người dùng tự cập nhật file `.env` thật của họ (không commit `.env`, chỉ sửa `.env.example`).

- [ ] **Step 5: Verify build Docker thật**

```bash
docker compose build frontend
docker compose up -d
docker compose ps
curl -sf http://localhost:3000/health
```
Expected: build thành công, container `frontend` healthy, `/health` trả `OK`. Mở `http://localhost:3000` xác nhận app load đúng, `/dashboard`, `/sources`, `/reports` hoạt động qua nginx (F5 ở `/sources` không bị 404 — xác nhận SPA fallback hoạt động).

- [ ] **Step 6: Commit**

```bash
git add frontend/Dockerfile frontend/nginx.frontend.conf docker-compose.yml .env.example
git commit -m "feat: chuyển frontend sang build tĩnh Vite + serve qua nginx"
```

---

## Task 15: Dọn dẹp cuối + verify toàn app

**Files:** không tạo file mới, chỉ verify.

- [ ] **Step 1: Build production**

Run: `cd frontend && npm run build`
Expected: build thành công, không lỗi TS.

- [ ] **Step 2: Grep xác nhận không còn sót import Next.js/react-query/zustand/auth**

```bash
cd frontend/src
grep -rn "next/\|@tanstack/react-query\|zustand\|useAuthStore\|PermissionGuard\|/login" . || echo "CLEAN"
```
Expected: `CLEAN` (không match nào).

- [ ] **Step 3: Duyệt thủ công toàn bộ sidebar**

`npm run dev`, click từng menu item (bao gồm mở submenu 2 cấp "Người dùng & phân quyền"), xác nhận: highlight đúng, mỗi trang mock render không lỗi console, `/sources` + `/reports` vẫn hoạt động thật như đã verify ở Task 5-6.

- [ ] **Step 4: Commit cuối nếu có phát sinh**

```bash
git add -A
git commit -m "chore: dọn dẹp cuối sau khi hoàn thành migration Vite"
```
(Bỏ qua nếu không có gì thay đổi.)

---

## Self-review

- **Spec coverage:** đủ scaffold (T1), routing+layout (T2), common+mock data (T3), Dashboard (T4), Sources thật (T5), Reports thật 2 trang (T6), 7 nhóm trang mock (T7-13), Docker/nginx (T14), verify cuối (T15) — khớp toàn bộ bảng phân loại trang đã chốt khi brainstorm.
- **Placeholder scan:** các task port-mock (T7-13) dùng "quy trình chuyển đổi cơ học" thay vì code đầy đủ — đây là quyết định phạm vi có chủ đích, đã giải thích rõ lý do ở đầu file, không phải placeholder mơ hồ kiểu "làm giống Task N".
- **Type consistency:** `SourceItem` định nghĩa 1 nơi (`Reports/SourceSidebar.tsx`), `API_BASE` 1 nơi (`lib/api.ts`), `HistoryEntry`/`JobStatus`/`CrawledArticle` giữ nguyên tên/shape giữa `Reports/index.tsx` và `Reports/ReportCreate.tsx` đúng với API contract đã biết.
- **Rủi ro cao nhất:** Task 6 (Reports) — đã note rõ khác biệt hành vi so với bản Next.js (F5-recovery đơn giản hơn vì không còn modal) và yêu cầu verify bằng job thật bắt buộc.
