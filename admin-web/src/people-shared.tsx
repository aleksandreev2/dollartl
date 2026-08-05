import React from "react";

export type UserRow = {
  id: string;
  telegram_id: number;
  telegram_username?: string | null;
  telegram_first_name?: string | null;
  telegram_last_name?: string | null;
  anonymous_id: number;
  display_name?: string | null;
  is_active: boolean;
  manual_download_access: boolean;
  last_seen_at?: string | null;
  created_at?: string | null;
  boosty_status: string;
  boosty_username?: string | null;
  grace_ends_at?: string | null;
  ban?: {
    id: string;
    type: string;
    reason: string;
    expires_at?: string | null;
  } | null;
};

export type UserPage = {
  page: number;
  page_size: number;
  total: number;
  pages: number;
  summary: Record<string, number>;
  items: UserRow[];
};

export type Dossier = {
  user: UserRow & { locale: string; updated_at?: string | null };
  access: {
    adult_consent: boolean;
    adult_consent_at?: string | null;
    blocked: boolean;
    effective_download_access: boolean;
    notifications: { new_titles: boolean; service: boolean };
    boosty?: Record<string, unknown> | null;
  };
  counts: Record<string, number>;
  bans: Array<Record<string, unknown>>;
  ban_history: Array<Record<string, unknown>>;
  boosty_periods: Array<Record<string, unknown>>;
  boosty_events: Array<Record<string, unknown>>;
  comments: Array<Record<string, unknown>>;
  ratings: Array<Record<string, unknown>>;
  reports: Array<Record<string, unknown>>;
  suggestions: Array<Record<string, unknown>>;
  downloads: Array<Record<string, unknown>>;
  follows: Array<Record<string, unknown>>;
  audit: Array<Record<string, unknown>>;
};

export type SelectionPreview = {
  requested: number;
  found: number;
  missing: number;
  eligible: number;
  inactive: number;
  banned: number;
  without_consent: number;
};

export const SELECTION_KEY = "dollartl.admin.selected-users.v1";

export function readSelection(): string[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(SELECTION_KEY) || "[]");
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === "string")
      : [];
  } catch {
    return [];
  }
}

export function ActionModal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  return (
    <div
      className="action-backdrop"
      role="presentation"
      onMouseDown={(event: React.MouseEvent<HTMLDivElement>) =>
        event.target === event.currentTarget && onClose()
      }
    >
      <section
        className={`action-modal${wide ? " wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header>
          <div><strong>{title}</strong></div>
          <button aria-label="Закрыть" onClick={onClose}>×</button>
        </header>
        <div className="action-modal-body">{children}</div>
      </section>
    </div>
  );
}
