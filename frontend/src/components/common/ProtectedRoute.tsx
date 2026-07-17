import { Spin } from "antd";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import ForbiddenPage from "@/pages/Forbidden";

export default function ProtectedRoute({ permission }: { permission?: string }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (permission && !user.permissions.includes(permission)) {
    return <ForbiddenPage />;
  }

  return <Outlet />;
}
