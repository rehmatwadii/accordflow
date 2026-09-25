import type { User } from "./types";
let token = "";
let refreshPending: Promise<User | null> | null = null;
export function setToken(value: string) {
  token = value;
}
export async function refreshSession(): Promise<User | null> {
  if (refreshPending) return refreshPending;
  refreshPending = (async () => {
    try {
      const response = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        credentials: "include",
        headers: { "X-LCV-Client": "workbench" },
      });
      if (!response.ok) return null;
      const data = await response.json();
      token = data.access_token;
      return data.user as User;
    } catch {
      return null;
    } finally {
      refreshPending = null;
    }
  })();
  return refreshPending;
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch("/api/v1" + path, {
    ...options,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && retry && !path.startsWith("/auth/")) {
    const user = await refreshSession();
    if (user) return api<T>(path, options, false);
    window.dispatchEvent(new Event("session-expired"));
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const fields = data.error?.details
      ?.map((d: { field: string }) => d.field.replace("body.", ""))
      .join(", ");
    throw new Error(
      (data.error?.message || "Unable to complete request") +
        (fields ? ` (${fields})` : "") +
        ` · ${data.error?.correlation_id || response.status}`,
    );
  }
  return response.json() as Promise<T>;
}
export async function download(path: string, filename: string) {
  const response = await fetch("/api/v1" + path, {
    headers: { Authorization: `Bearer ${token}` },
    credentials: "include",
  });
  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.error?.message || "Download failed");
  }
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
export function saveJson(data: unknown, filename: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
