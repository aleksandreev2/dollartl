import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import {
  Badge,
  ErrorBox,
  Field,
  Header,
  Icon,
  Loading,
  Notice,
  date,
  useData,
} from "./admin-ui";
import { DossierDrawer } from "./people-dossier";
import {
  ActionModal,
  readSelection,
  SELECTION_KEY,
  type SelectionPreview,
  type UserPage,
} from "./people-shared";

function SelectedBroadcastModal({
  userIds,
  onClose,
  onCreated,
}: {
  userIds: string[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const preview = useData(
    () => api<SelectionPreview>("/selected-users/preview", {
      method: "POST",
      body: JSON.stringify({ user_ids: userIds }),
    }),
    [userIds.join(",")],
  );
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    const form = new FormData(event.currentTarget);
    try {
      const sendNow = form.get("send_now") === "on";
      const scheduled = String(form.get("scheduled_at") || "");
      await api("/broadcasts", {
        method: "POST",
        body: JSON.stringify({
          audience_type: "selected",
          selected_user_ids: userIds,
          title_id: null,
          text: form.get("text"),
          button_text: form.get("button_text") || null,
          button_url: form.get("button_url") || null,
          scheduled_at: !sendNow && scheduled
            ? new Date(scheduled).toISOString()
            : null,
          send_now: sendNow,
        }),
      });
      onCreated();
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ActionModal title="Рассылка выбранным пользователям" onClose={onClose} wide>
      <form className="form" onSubmit={submit}>
        {notice && <ErrorBox text={notice}/>} 
        {preview.loading ? <Loading/> : preview.data && (
          <div className="selection-preview">
            <article><span>Выбрано</span><strong>{preview.data.requested}</strong></article>
            <article><span>Получат</span><strong>{preview.data.eligible}</strong></article>
            <article><span>Заблокированы</span><strong>{preview.data.banned}</strong></article>
            <article><span>Неактивны</span><strong>{preview.data.inactive}</strong></article>
          </div>
        )}
        <Field label="Текст"><textarea name="text" rows={8} maxLength={1024} required/></Field>
        <div className="row">
          <Field label="Текст кнопки"><input name="button_text" maxLength={64}/></Field>
          <Field label="URL кнопки"><input name="button_url" type="url"/></Field>
        </div>
        <Field label="Запланировать"><input name="scheduled_at" type="datetime-local"/></Field>
        <label className="checkbox"><input name="send_now" type="checkbox" defaultChecked/> Отправить при ближайшем цикле worker</label>
        <div className="modal-actions">
          <button type="button" onClick={onClose}>Отмена</button>
          <button className="primary" disabled={busy || !preview.data?.eligible}>{busy ? "Создаём…" : "Создать рассылку"}</button>
        </div>
      </form>
    </ActionModal>
  );
}

export function UsersWorkbenchView() {
  const [query, setQuery] = useState("");
  const [access, setAccess] = useState("all");
  const [userState, setUserState] = useState("all");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string[]>(readSelection);
  const [openUser, setOpenUser] = useState<string | null>(null);
  const [broadcastOpen, setBroadcastOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const state = useData(
    () => api<UserPage>(`/users/workbench?q=${encodeURIComponent(query)}&access=${access}&state=${userState}&page=${page}&page_size=30`),
    [query, access, userState, page],
  );

  useEffect(() => localStorage.setItem(SELECTION_KEY, JSON.stringify(selected)), [selected]);
  useEffect(() => setPage(1), [query, access, userState]);
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const visibleIds = state.data?.items.map((item) => item.id) || [];
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedSet.has(id));

  function toggle(id: string) {
    setSelected((current) => current.includes(id)
      ? current.filter((item) => item !== id)
      : [...current, id]);
  }

  function toggleVisible() {
    setSelected((current) => allVisibleSelected
      ? current.filter((id) => !visibleIds.includes(id))
      : Array.from(new Set([...current, ...visibleIds])));
  }

  return (
    <section className="page people-page">
      <Header
        title="Пользователи"
        description="Карточки, доступ, блокировки и выбранные аудитории."
        action={<button className="with-icon" onClick={state.reload}><Icon name="refresh"/>Обновить</button>}
      />
      {notice && <Notice text={notice}/>} 
      {state.error && <ErrorBox text={state.error}/>} 
      {state.data && (
        <div className="mini-metrics user-summary">
          <article><span>Всего</span><strong>{state.data.summary.users || 0}</strong></article>
          <article><span>VIP</span><strong>{state.data.summary.active_vip || 0}</strong></article>
          <article><span>Grace</span><strong>{state.data.summary.grace_period || 0}</strong></article>
          <article><span>Заблокированы</span><strong>{state.data.summary.banned || 0}</strong></article>
        </div>
      )}
      <div className="toolbar people-toolbar">
        <label className="toolbar-search">
          <Icon name="search"/>
          <input
            value={query}
            onChange={(event: React.ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)}
            placeholder="Anonymous 1, username, Telegram ID или имя"
          />
        </label>
        <select value={access} onChange={(event: React.ChangeEvent<HTMLSelectElement>) => setAccess(event.target.value)}>
          <option value="all">Любой доступ</option><option value="vip">VIP</option><option value="grace">Grace</option><option value="manual">Ручной</option><option value="standard">Standard</option>
        </select>
        <select value={userState} onChange={(event: React.ChangeEvent<HTMLSelectElement>) => setUserState(event.target.value)}>
          <option value="all">Любое состояние</option><option value="active">Активные</option><option value="banned">Заблокированные</option><option value="inactive">Неактивные</option>
        </select>
      </div>
      {state.loading || !state.data ? <Loading/> : (
        <div className="work-table people-table">
          <table>
            <thead><tr><th><input type="checkbox" checked={allVisibleSelected} onChange={toggleVisible}/></th><th>Пользователь</th><th>Telegram</th><th>Доступ</th><th>Состояние</th><th>Последняя активность</th><th/></tr></thead>
            <tbody>{state.data.items.map((item) => (
              <tr key={item.id} className={selectedSet.has(item.id) ? "selected" : ""}>
                <td><input type="checkbox" checked={selectedSet.has(item.id)} onChange={() => toggle(item.id)}/></td>
                <td><strong>{item.display_name || `Anonymous ${item.anonymous_id}`}</strong><small>{item.telegram_first_name || ""} {item.telegram_last_name || ""}</small></td>
                <td><span>{item.telegram_username ? `@${item.telegram_username}` : "без username"}</span><small>{item.telegram_id}</small></td>
                <td><Badge value={item.boosty_status}/>{item.manual_download_access && <small>Ручной доступ</small>}</td>
                <td>{item.ban ? <><span className="user-state blocked">Заблокирован</span><small>{item.ban.reason}</small></> : <span className={`user-state ${item.is_active ? "active" : "inactive"}`}>{item.is_active ? "Активен" : "Неактивен"}</span>}</td>
                <td>{date(item.last_seen_at)}</td>
                <td><button onClick={() => setOpenUser(item.id)}>Открыть</button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      {state.data && (
        <div className="pager">
          <button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Назад</button>
          <span>Страница {state.data.page} из {state.data.pages} · {state.data.total} пользователей</span>
          <button disabled={page >= state.data.pages} onClick={() => setPage((value) => value + 1)}>Дальше</button>
        </div>
      )}
      {selected.length > 0 && (
        <div className="selection-tray">
          <div><strong>Выбрано: {selected.length}</strong><small>Набор сохраняется между разделами и перезапусками Mini App.</small></div>
          <div><button onClick={() => setSelected([])}>Очистить</button><button className="primary" onClick={() => setBroadcastOpen(true)}><Icon name="send"/>Создать рассылку</button></div>
        </div>
      )}
      {openUser && <DossierDrawer userId={openUser} onClose={() => setOpenUser(null)} onChanged={state.reload}/>} 
      {broadcastOpen && (
        <SelectedBroadcastModal
          userIds={selected}
          onClose={() => setBroadcastOpen(false)}
          onCreated={() => {
            setBroadcastOpen(false);
            setSelected([]);
            setNotice("Рассылка выбранной аудитории создана.");
          }}
        />
      )}
    </section>
  );
}
