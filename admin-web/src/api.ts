declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string;
        ready(): void;
        expand(): void;
        setHeaderColor?(color: string): void;
        setBackgroundColor?(color: string): void;
        showConfirm?(message: string, callback: (confirmed: boolean) => void): void;
      };
    };
  }
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  const initData = window.Telegram?.WebApp?.initData || "";
  if (initData) headers.set("X-Telegram-Init-Data", initData);
  const devId = import.meta.env.VITE_ADMIN_DEVELOPMENT_ID;
  if (devId) headers.set("X-Admin-Development-Id", devId);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE}/admin/api${path}`, { ...options, headers });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const payload = await response.json();
      detail = payload.detail || JSON.stringify(payload);
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.status === 204 ? (undefined as T) : response.json() as Promise<T>;
}

export function initializeTelegram(): void {
  const webApp = window.Telegram?.WebApp;
  if (!webApp) return;
  webApp.ready();
  webApp.expand();
  webApp.setHeaderColor?.("#0d1017");
  webApp.setBackgroundColor?.("#0d1017");
}

export function confirmAction(message: string): Promise<boolean> {
  const webApp = window.Telegram?.WebApp;
  if (webApp?.showConfirm) return new Promise((resolve) => webApp.showConfirm!(message, resolve));
  return Promise.resolve(window.confirm(message));
}
