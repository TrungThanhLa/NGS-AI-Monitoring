import { Outlet } from "react-router-dom";

export default function AuthLayout() {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(145deg, #0A1D55 0%, #0B2262 45%, #00859A 100%)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
      }}
    >
      <Outlet />
    </div>
  );
}
