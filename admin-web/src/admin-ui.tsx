import React, { useCallback, useEffect, useState } from "react";

export type Section =
  | "overview"
  | "catalog"
  | "users"
  | "suggestions"
  | "community"
  | "boosty"
  | "broadcasts"
  | "channel"
  | "files"
  | "audit"
  | "settings";

export type IconName =
  | "dashboard"
  | "book"
  | "users"
  | "sparkles"
  | "message"
  | "diamond"
  | "send"
  | "telegram"
  | "folder"
  | "history"
  | "settings"
  | "search"
  | "menu"
  | "chevron"
  | "alert"
  | "shield"
  | "refresh";

export type SectionDefinition = {
  id: Section;
  label: string;
  description: string;
  icon: IconName;
};

export const sections: SectionDefinition[] = [
  { id: "overview", label: "Обзор", description: "Метрики и срочные задачи", icon: "dashboard" },
  { id: "catalog", label: "Тайтлы и пакеты", description: "Каталог, файлы и публикации", icon: "book" },
  { id: "users", label: "Пользователи", description: "Поиск, доступ и блокировки", icon: "users" },
  { id: "suggestions", label: "Предложения", description: "Заявки и обязательные raw-файлы", icon: "sparkles" },
  { id: "community", label: "Сообщество", description: "Комментарии, оценки и жалобы", icon: "message" },
  { id: "boosty", label: "Boosty", description: "VIP-доступ и синхронизация", icon: "diamond" },
  { id: "broadcasts", label: "Рассылки", description: "Ручные и отложенные отправки", icon: "send" },
  { id: "channel", label: "Telegram-канал", description: "Автопубликации и статистика", icon: "telegram" },
  { id: "files", label: "Файлы и кэш", description: "S3, версии и Telegram file_id", icon: "folder" },
  { id: "audit", label: "Журнал действий", description: "История административных операций", icon: "history" },
  { id: "settings", label: "Настройки", description: "Runtime overrides и диагностика", icon: "settings" },
];

const labels: Record<string, string> = {
  draft: "Черновик",
  scheduled: "Запланировано",
  processing: "Выполняется",
  completed: "Завершено",
  failed: "Ошибка",
  cancelled: "Отменено",
  under_review: "На проверке",
  accepted: "Принято",
  translated: "Переведено",
  rejected: "Отклонено",
  active_vip: "VIP",
  grace_period: "Grace",
  expired: "Истекло",
  unverified: "Не привязан",
  valid: "Проверено",
  warning: "Предупреждение",
  error: "Ошибка",
  overridden: "Подтверждено",
  pending: "Ожидает",
  open: "Открыта",
  in_progress: "В работе",
  resolved: "Решена",
  reviewed: "Проверено",
  fixed: "Исправлено",
  dismissed: "Отклонено",
};

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
  const paths: Record<IconName, React.ReactNode> = {
    dashboard: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="4" rx="2"/><rect x="14" y="11" width="7" height="10" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/></>,
    book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H13v16h4.5a2.5 2.5 0 0 1 2.5 2.5z"/></>,
    users: <><circle cx="9" cy="8" r="3"/><path d="M3.5 20a5.5 5.5 0 0 1 11 0"/><circle cx="17" cy="9" r="2.5"/><path d="M15.5 14.5A5 5 0 0 1 21 20"/></>,
    sparkles: <><path d="m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2z"/><path d="m18.5 14 .7 2.3 2.3.7-2.3.7-.7 2.3-.7-2.3-2.3-.7 2.3-.7z"/></>,
    message: <><path d="M21 12a8 8 0 0 1-8 8H6l-4 2 1.4-4.2A8 8 0 1 1 21 12Z"/><path d="M8 12h.01M12 12h.01M16 12h.01"/></>,
    diamond: <><path d="m12 3 8 6-8 12L4 9z"/><path d="m4 9 8 3 8-3M9 4.7 12 12l3-7.3"/></>,
    send: <><path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/></>,
    telegram: <><path d="m21 4-3 16-6-4-4 3 1-5-6-3z"/><path d="m9 14 9-7"/></>,
    folder: <path d="M3 6.5A2.5 2.5 0 0 1 5.5 4H10l2 2h6.5A2.5 2.5 0 0 1 21 8.5v8A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5z"/>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
    menu: <path d="M4 7h16M4 12h16M4 17h16"/>,
    chevron: <path d="m9 18 6-6-6-6"/>,
    alert: <><path d="M12 3 2.8 20h18.4z"/><path d="M12 9v4M12 17h.01"/></>,
    shield: <><path d="M12 3 20 6v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="m9 12 2 2 4-4"/></>,
    refresh: <><path d="M20 7v5h-5"/><path d="M4 17v-5h5"/><path d="M6.1 9A7 7 0 0 1 18 7l2 5M18 15a7 7 0 0 1-11.9 2L4 12"/></>,
  };
  return <svg {...common}>{paths[name]}</svg>;
}

export function useData<T>(loader: () => Promise<T>, dependencies: React.DependencyList = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const reload = useCallback(async () => {
    setLoading(true);
    setError("");
    try { setData(await loader()); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setLoading(false); }
  }, dependencies); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => void reload(), [reload]);
  return { data, loading, error, reload };
}

export function date(value?: string | null) {
  return value ? new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)) : "—";
}
export function bytes(value: number) {
  const units = ["Б", "КБ", "МБ", "ГБ"];
  let number = value;
  let index = 0;
  while (number >= 1024 && index < 3) { number /= 1024; index += 1; }
  return `${number.toFixed(index ? 1 : 0)} ${units[index]}`;
}
export function Badge({ value }: { value: string }) { return <span className={`badge badge-${value.replaceAll("_", "-")}`}>{labels[value] || value}</span>; }
export function Header({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) { return <header className="page-head"><div><h1>{title}</h1><p>{description}</p></div>{action}</header>; }
export function ErrorBox({ text }: { text: string }) { return <div className="error-box">{text}</div>; }
export function Notice({ text }: { text: string }) { return <div className="notice">{text}</div>; }
export function Loading() { return <div className="loading"><span className="spinner"/>Загрузка…</div>; }
export function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="field"><span>{label}</span>{children}</label>; }
