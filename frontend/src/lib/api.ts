export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) return null;

  const res = await fetch(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) return null;

  const data = await res.json();
  localStorage.setItem("access_token", data.access_token);
  return data.access_token as string;
}

// Wrapper cho mọi API call cần auth — tự gắn Bearer token, tự refresh 1 lần nếu
// access token hết hạn (401), tự điều hướng về /login nếu refresh cũng thất bại.
export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = localStorage.getItem("access_token");
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response = await fetch(`${API_BASE}${path}`, { ...init, headers });

  if (response.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers.set("Authorization", `Bearer ${newToken}`);
      response = await fetch(`${API_BASE}${path}`, { ...init, headers });
    } else {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      window.location.href = "/login";
    }
  }

  return response;
}
