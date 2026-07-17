import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

export type CurrentUser = {
  user_id: string;
  username: string;
  full_name: string | null;
  email: string | null;
  roles: string[];
  permissions: string[];
};

type AuthContextValue = {
  user: CurrentUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchMe(accessToken: string): Promise<CurrentUser> {
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error("unauthorized");
  return res.json();
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setLoading(false);
      return;
    }
    fetchMe(token)
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(username: string, password: string) {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: "Đăng nhập thất bại" }));
      throw new Error(body.detail ?? "Đăng nhập thất bại");
    }
    const data = await res.json();
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    setUser(data.user);
  }

  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setUser(null);
  }

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth() phải được gọi bên trong AuthProvider");
  return ctx;
}
