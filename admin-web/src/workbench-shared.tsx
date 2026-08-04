import React, { ChangeEvent, FormEvent, MouseEvent, useMemo, useState } from "react";
import { Badge, ErrorBox, Header, Icon, Loading, Notice, bytes, date, useData } from "./admin-ui";

export type PageEnvelope<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type BoostyItem = {
  id: string;
  user_id: string;
  anonymous_id: number;
  display_name: string;
  telegram_id: number;
  telegram_username?: string | null;
  manual_download_access: boolean;
  boosty_user_id?: string | null;
  boosty_username?: string | null;
  tier_id?: string | null;
  tier_name?: string | null;
  status: string;
  verified_at?: string | null;
  last_checked_at?: string | null;
  last_successful_check_at?: string | null;
  membership_expires_at?: string | null;
  grace_ends_at?: string | null;
  last_error_code?: string | null;
  last_error_message?: string | null;
  updated_at?: string | null;
};

export type BoostyResponse = PageEnvelope<BoostyItem> & {
  summary: Record<string, number>;
  recent_syncs: Array<{
    id: string;
    run_type: string;
    status: string;
    started_at?: string | null;
    finished_at?: string | null;
    scanned_count: number;
    matched_count: number;
    changed_count: number;
    error_count: number;
  }>;
  recent_errors: Array<{
    id: string;
    user_id?: string | null;
    error_code: string;
    message: string;
    created_at?: string | null;
  }>;
};

export type ChannelItem = {
  id: string;
  target_type: string;
  target_id: string;
  telegram_chat_id: string;
  telegram_message_id?: number | null;
  status: string;
  error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ChannelResponse = PageEnvelope<ChannelItem> & {
  summary: Record<string, number>;
  channel_username: string;
  channel_posts_enabled: boolean;
};

export type FileItem = {
  id: string;
  release_file_id: string;
  release_id: string;
  title_id: string;
  title: string;
  release_label: string;
  file_kind: string;
  version: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  telegram_cached: boolean;
  is_active: boolean;
  created_at?: string | null;
};

export type FilesResponse = PageEnvelope<FileItem> & {
  summary: { active: number; cached: number; bytes: number };
};

export type AuditItem = {
  id: string;
  actor_telegram_id?: number | null;
  action: string;
  entity_type?: string | null;
  entity_id?: string | null;
  payload: Record<string, unknown>;
  correlation_id?: string | null;
  created_at?: string | null;
};

export type AuditResponse = PageEnvelope<AuditItem> & {
  actions: string[];
  entity_types: string[];
};

export type SettingsResponse = {
  notice: string;
  overrides: Array<{
    id: string;
    key: string;
    value: unknown;
    description?: string | null;
    updated_at?: string | null;
  }>;
  environment: Array<{ key: string; value: unknown; source: string }>;
};

export function Pager({ page, pages, total, onPage }: { page: number; pages: number; total: number; onPage: (value: number) => void }) {
  return (
    <div className="wb-pager">
      <span>Всего: <b>{total}</b></span>
      <div>
        <button disabled={page <= 1} onClick={() => onPage(page - 1)}>Назад</button>
        <span>{page} / {pages}</span>
        <button disabled={page >= pages} onClick={() => onPage(page + 1)}>Дальше</button>
      </div>
    </div>
  );
}

export function StatCards({ entries }: { entries: Array<[string, number | string, string]> }) {
  return <div className="wb-stats">{entries.map(([label, value, tone]) => <article key={label} data-tone={tone}><span>{label}</span><strong>{value}</strong></article>)}</div>;
}

export function Empty({ text }: { text: string }) {
  return <div className="wb-empty"><Icon name="search" size={28}/><strong>{text}</strong><span>Измените фильтры или обновите данные.</span></div>;
}

export function ReasonDialog({ open, title, enabled, onClose, onSubmit }: { open: boolean; title: string; enabled: boolean; onClose: () => void; onSubmit: (reason: string) => Promise<void> }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!open) return null;
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try { await onSubmit(reason.trim()); setReason(""); onClose(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  }
  return <div className="wb-modal-backdrop" role="presentation" onMouseDown={(event: MouseEvent<HTMLDivElement>) => event.target === event.currentTarget && onClose()}><form className="wb-modal" onSubmit={submit}><header><div><h3>{enabled ? "Выдать ручной доступ" : "Отключить ручной доступ"}</h3><p>{title}</p></div><button type="button" aria-label="Закрыть" onClick={onClose}>×</button></header>{error && <ErrorBox text={error}/>}<label><span>Причина для audit log</span><textarea autoFocus value={reason} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setReason(event.target.value)} minLength={3} maxLength={500} required rows={4}/></label><footer><button type="button" onClick={onClose}>Отмена</button><button className="primary" disabled={busy || reason.trim().length < 3}>{busy ? "Сохраняем…" : "Подтвердить"}</button></footer></form></div>;
}
