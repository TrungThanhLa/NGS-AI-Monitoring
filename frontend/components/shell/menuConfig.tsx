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

// Map route -> tiêu đề hiển thị ở breadcrumb header (AppShell.tsx), tách riêng khỏi
// sidebarItems vì label trong Menu item là JSX/ReactNode, còn breadcrumb cần chuỗi thuần.
export const pageTitles: Record<string, string> = {
  "/dashboard": "Tổng quan",
  "/campaigns": "Chiến dịch giám sát",
  "/sources": "Nguồn dữ liệu",
  "/contents": "Nội dung",
  "/alerts": "Cảnh báo",
  "/cases": "Vụ việc",
  "/reports": "Báo cáo",
  "/jobs": "Lịch chạy & Jobs",
  "/system": "Cấu hình hệ thống",
  "/system/master-data": "Dữ liệu dùng chung",
  "/system/users": "Người dùng & phân quyền",
  "/system/audit-logs": "Nhật ký hệ thống",
  "/system/alert-rules": "Cấu hình cảnh báo",
  "/system/crawler-settings": "Cấu hình Crawler",
  "/system/report-settings": "Cấu hình báo cáo",
  "/system/settings": "Tham số hệ thống",
};

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
