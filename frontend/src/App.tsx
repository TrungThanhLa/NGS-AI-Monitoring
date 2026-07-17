import { Navigate, Route, Routes } from "react-router-dom";
import MainLayout from "@/layouts/MainLayout";
import AuthLayout from "@/layouts/AuthLayout";
import LoginPage from "@/pages/Login";
import ProtectedRoute from "@/components/common/ProtectedRoute";
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
import ProfilePage from "@/pages/Profile";
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
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route element={<MainLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/profile" element={<ProfilePage />} />

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
      </Route>
    </Routes>
  );
}
