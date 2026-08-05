import React, { FormEvent, useState } from "react";
import { api, confirmAction } from "./api";
import {
  Badge,
  ErrorBox,
  Field,
  Icon,
  Loading,
  Notice,
  date,
  useData,
} from "./admin-ui";
import { ActionModal, type Dossier, type UserRow } from "./people-shared";

export function DossierDrawer({
  userId,
  onClose,
  onChanged,
}: {
  userId: string;
  onClose: () => void;
  onChanged: () => Promise<void>;
}) {
  const state = useData(() => api<Dossier>(`/users/${userId}/dossier`), [userId]);
  const [tab, setTab] = useState<"summary" | "activity" | "access">("summary");
  const [notice, setNotice] = useState("");
  const [banOpen, setBanOpen] = useState(false);
  const [accessOpen, setAccessOpen] = useState(false);

  async function unban() {
    if (!(await confirmAction("Снять все активные блокировки пользователя?"))) return;
    try {
      await api(`/users/${userId}/unban`, { method: "POST" });
      setNotice("Активные блокировки сняты.");
      await Promise.all([state.reload(), onChanged()]);
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : String(cause));
    }
  }

  return (
    <>
      <div
        className="drawer-backdrop"
        onMouseDown={(event: React.MouseEvent<HTMLDivElement>) =>
          event.target === event.currentTarget && onClose()
        }
      >
        <aside className="user-drawer">
          <header className="drawer-head">
            <div>
              <strong>Карточка пользователя</strong>
              <small>Доступ, история и действия</small>
            </div>
            <button aria-label="Закрыть" onClick={onClose}>×</button>
          </header>
          {notice && <Notice text={notice}/>} 
          {state.error && <ErrorBox text={state.error}/>} 
          {state.loading || !state.data ? <Loading/> : <>
            <section className="identity-card">
              <div className="identity-avatar">A{state.data.user.anonymous_id}</div>
              <div>
                <h2>{state.data.user.display_name || `Anonymous ${state.data.user.anonymous_id}`}</h2>
                <p>{state.data.user.telegram_username ? `@${state.data.user.telegram_username}` : "без username"} · {state.data.user.telegram_id}</p>
                <div className="identity-badges">
                  <Badge value={state.data.user.boosty_status}/>
                  {state.data.access.blocked && <Badge value="failed"/>}
                  {state.data.user.manual_download_access && <Badge value="overridden"/>}
                </div>
              </div>
            </section>
            <div className="drawer-actions">
              <button onClick={() => setAccessOpen(true)}><Icon name="diamond"/>Ручной доступ</button>
              {state.data.access.blocked ? (
                <button onClick={unban}><Icon name="shield"/>Снять бан</button>
              ) : (
                <button className="danger" onClick={() => setBanOpen(true)}><Icon name="shield"/>Заблокировать</button>
              )}
            </div>
            <div className="tabs dossier-tabs">
              <button className={tab === "summary" ? "active" : ""} onClick={() => setTab("summary")}>Сводка</button>
              <button className={tab === "activity" ? "active" : ""} onClick={() => setTab("activity")}>Активность</button>
              <button className={tab === "access" ? "active" : ""} onClick={() => setTab("access")}>Доступ</button>
            </div>
            {tab === "summary" && <DossierSummary dossier={state.data}/>} 
            {tab === "activity" && <DossierActivity dossier={state.data}/>} 
            {tab === "access" && <DossierAccess dossier={state.data}/>} 
          </>}
        </aside>
      </div>
      {banOpen && state.data && (
        <BanModal
          user={state.data.user}
          onClose={() => setBanOpen(false)}
          onDone={async () => {
            setBanOpen(false);
            await Promise.all([state.reload(), onChanged()]);
          }}
        />
      )}
      {accessOpen && state.data && (
        <ManualAccessModal
          user={state.data.user}
          onClose={() => setAccessOpen(false)}
          onDone={async () => {
            setAccessOpen(false);
            await Promise.all([state.reload(), onChanged()]);
          }}
        />
      )}
    </>
  );
}

function DossierSummary({ dossier }: { dossier: Dossier }) {
  const rows: Array<[string, number]> = [
    ["Комментарии", dossier.counts.comments || 0],
    ["Оценки", dossier.counts.ratings || 0],
    ["Жалобы", dossier.counts.reports || 0],
    ["Предложения", dossier.counts.suggestions || 0],
    ["Скачивания", dossier.counts.downloads || 0],
    ["Подписки", dossier.counts.follows || 0],
  ];
  return (
    <div className="dossier-content">
      <div className="mini-metrics">
        {rows.map(([label, value]) => (
          <article key={label}><span>{label}</span><strong>{value}</strong></article>
        ))}
      </div>
      <section className="detail-grid">
        <article><span>Создан</span><strong>{date(dossier.user.created_at)}</strong></article>
        <article><span>Последняя активность</span><strong>{date(dossier.user.last_seen_at)}</strong></article>
        <article><span>Возрастное согласие</span><strong>{dossier.access.adult_consent ? "Принято" : "Нет"}</strong></article>
        <article><span>Скачивания</span><strong>{dossier.access.effective_download_access ? "Разрешены" : "Ограничены"}</strong></article>
      </section>
      <h3>Последние скачивания</h3>
      <CompactRows
        items={dossier.downloads}
        titleKey="title"
        meta={(item) => `${String(item.release || "")} · ${String(item.method || "")} · ${date(item.created_at as string)}`}
      />
      <h3>Подписки на тайтлы</h3>
      <CompactRows items={dossier.follows} titleKey="title" meta={(item) => date(item.created_at as string)}/>
    </div>
  );
}

function DossierActivity({ dossier }: { dossier: Dossier }) {
  return (
    <div className="dossier-content">
      <h3>Комментарии</h3>
      <CompactRows items={dossier.comments} titleKey="body" meta={(item) => `${item.is_deleted ? "Удалён" : "Активен"} · ${date(item.created_at as string)}`}/>
      <h3>Оценки</h3>
      <CompactRows items={dossier.ratings} titleKey="title" meta={(item) => `${String(item.score || 0)}/5 · ${String(item.release || "")} · ${String(item.status || "")}`}/>
      <h3>Жалобы</h3>
      <CompactRows items={dossier.reports} titleKey="description" meta={(item) => `${String(item.category || "")} · ${String(item.status || "")} · ${date(item.created_at as string)}`}/>
      <h3>Предложения</h3>
      <CompactRows items={dossier.suggestions} titleKey="title" meta={(item) => `${String(item.status || "")} · ${date(item.submitted_at as string)}`}/>
      <h3>Административный журнал</h3>
      <CompactRows items={dossier.audit} titleKey="action" meta={(item) => `${date(item.created_at as string)} · ${String(item.correlation_id || "без correlation ID")}`}/>
    </div>
  );
}

function DossierAccess({ dossier }: { dossier: Dossier }) {
  const boosty = dossier.access.boosty || {};
  return (
    <div className="dossier-content">
      <section className="detail-grid">
        <article><span>Boosty</span><strong>{String(boosty.status || "Не привязан")}</strong></article>
        <article><span>Boosty username</span><strong>{String(boosty.username || "—")}</strong></article>
        <article><span>Тариф</span><strong>{String(boosty.tier_name || "—")}</strong></article>
        <article><span>Grace до</span><strong>{date(boosty.grace_ends_at as string)}</strong></article>
      </section>
      <h3>Периоды доступа</h3>
      <CompactRows items={dossier.boosty_periods} titleKey="status" meta={(item) => `${String(item.reason || "")} · ${date(item.starts_at as string)} → ${date(item.ends_at as string)}`}/>
      <h3>События доступа</h3>
      <CompactRows items={dossier.boosty_events} titleKey="event_type" meta={(item) => `${date(item.created_at as string)}${item.last_error ? ` · ${String(item.last_error)}` : ""}`}/>
      <h3>Блокировки</h3>
      <CompactRows items={dossier.bans} titleKey="public_reason" meta={(item) => `${String(item.type || "")} · ${item.is_active ? "активна" : "закрыта"} · до ${date(item.expires_at as string)}`}/>
    </div>
  );
}

function CompactRows({
  items,
  titleKey,
  meta,
}: {
  items: Array<Record<string, unknown>>;
  titleKey: string;
  meta: (item: Record<string, unknown>) => string;
}) {
  if (!items.length) return <div className="empty-inline">Нет данных</div>;
  return (
    <div className="compact-rows">
      {items.slice(0, 12).map((item, index) => (
        <article key={String(item.id || item.title_id || index)}>
          <strong>{String(item[titleKey] || "—")}</strong>
          <small>{meta(item)}</small>
        </article>
      ))}
    </div>
  );
}

function BanModal({
  user,
  onClose,
  onDone,
}: {
  user: UserRow;
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const type = String(form.get("ban_type"));
    const days = Math.max(1, Number(form.get("days") || 7));
    try {
      await api(`/users/${user.id}/ban`, {
        method: "POST",
        body: JSON.stringify({
          ban_type: type,
          public_reason: form.get("public_reason"),
          internal_note: form.get("internal_note") || null,
          reason_template: form.get("reason_template") || null,
          expires_at: type === "permanent"
            ? null
            : new Date(Date.now() + days * 86400000).toISOString(),
        }),
      });
      await onDone();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }
  return (
    <ActionModal title={`Блокировка Anonymous ${user.anonymous_id}`} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        {error && <ErrorBox text={error}/>} 
        <Field label="Тип">
          <select name="ban_type"><option value="temporary">Временная</option><option value="permanent">Постоянная</option></select>
        </Field>
        <Field label="Срок временной блокировки, дней"><input name="days" type="number" min="1" defaultValue="7"/></Field>
        <Field label="Шаблон причины">
          <select name="reason_template"><option value="">Без шаблона</option><option value="spam">Спам</option><option value="abuse">Оскорбления</option><option value="rules">Нарушение правил</option><option value="unsafe_file">Опасный файл</option></select>
        </Field>
        <Field label="Публичная причина"><textarea name="public_reason" rows={4} required minLength={3}/></Field>
        <Field label="Внутренняя заметка"><textarea name="internal_note" rows={3}/></Field>
        <div className="modal-actions"><button type="button" onClick={onClose}>Отмена</button><button className="danger" disabled={busy}>{busy ? "Сохраняем…" : "Заблокировать"}</button></div>
      </form>
    </ActionModal>
  );
}

function ManualAccessModal({
  user,
  onClose,
  onDone,
}: {
  user: UserRow;
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api(`/boosty/users/${user.id}/manual-access`, {
        method: "POST",
        body: JSON.stringify({
          enabled: form.get("enabled") === "true",
          reason: form.get("reason"),
        }),
      });
      await onDone();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }
  return (
    <ActionModal title={`Ручной доступ · Anonymous ${user.anonymous_id}`} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        {error && <ErrorBox text={error}/>} 
        <Field label="Состояние">
          <select name="enabled" defaultValue={String(!user.manual_download_access)}>
            <option value="true">Разрешить скачивания</option>
            <option value="false">Снять ручной доступ</option>
          </select>
        </Field>
        <Field label="Причина"><textarea name="reason" rows={4} required minLength={3}/></Field>
        <div className="modal-actions"><button type="button" onClick={onClose}>Отмена</button><button className="primary">Применить</button></div>
      </form>
    </ActionModal>
  );
}
