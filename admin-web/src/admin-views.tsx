import React, { FormEvent, useMemo, useState } from "react";
import { api, confirmAction } from "./api";
import type { BroadcastItem } from "./types";
import { Badge, ErrorBox, Field, Header, Icon, Loading, date, useData, useToast } from "./admin-ui";

type RetryPreview = {
  requested: number;
  found: number;
  eligible_broadcasts: number;
  retriable_recipients: number;
  missing: number;
  items: Array<{ id: string; recipients: number }>;
};
type RetryModal = { key: string; preview: RetryPreview } | null;

function operationKey() {
  return `broadcast-retry:${Date.now()}:${crypto.randomUUID()}`;
}

export function BroadcastsView() {
  const [status, setStatus] = useState("all");
  const [created, setCreated] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [retryModal, setRetryModal] = useState<RetryModal>(null);
  const [busy, setBusy] = useState(false);
  const state = useData(() => api<BroadcastItem[]>("/broadcasts?limit=300"), []);
  const { push } = useToast();
  const items = useMemo(
    () => (state.data || []).filter((item) => status === "all" || item.status === status),
    [state.data, status],
  );

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    try {
      const item = await api<{ id: string }>("/broadcasts", {
        method: "POST",
        body: JSON.stringify({
          audience_type: form.get("audience_type"),
          title_id: form.get("title_id") || null,
          text: form.get("text"),
          button_text: form.get("button_text") || null,
          button_url: form.get("button_url") || null,
          scheduled_at: form.get("scheduled_at")
            ? new Date(String(form.get("scheduled_at"))).toISOString()
            : null,
          send_now: form.get("send_now") === "on",
          selected_user_ids: [],
        }),
      });
      setCreated(item.id);
      formElement.reset();
      await state.reload();
      push(`Рассылка создана: ${item.id}`, "success");
    } catch (cause) {
      push(cause instanceof Error ? cause.message : String(cause), "error");
    } finally {
      setBusy(false);
    }
  }

  async function uploadPhoto(file: File) {
    if (!created) {
      push("Сначала создайте рассылку.", "error");
      return;
    }
    const body = new FormData();
    body.set("file", file);
    try {
      await api(`/broadcasts/${created}/photo`, { method: "POST", body });
      push("Фото прикреплено.", "success");
    } catch (cause) {
      push(cause instanceof Error ? cause.message : String(cause), "error");
    }
  }

  async function previewRetry() {
    if (!selected.length) return;
    const key = operationKey();
    setBusy(true);
    try {
      const preview = await api<RetryPreview>("/broadcasts/retry-failed", {
        method: "POST",
        body: JSON.stringify({ broadcast_ids: selected, dry_run: true, idempotency_key: key }),
      });
      setRetryModal({ key, preview });
    } catch (cause) {
      push(cause instanceof Error ? cause.message : String(cause), "error");
    } finally {
      setBusy(false);
    }
  }

  async function executeRetry() {
    if (!retryModal) return;
    const accepted = await confirmAction(
      `Вернуть в очередь ${retryModal.preview.eligible_broadcasts} рассылок и ${retryModal.preview.retriable_recipients} получателей?`,
    );
    if (!accepted) return;
    setBusy(true);
    try {
      const result = await api<RetryPreview & { replayed: boolean }>("/broadcasts/retry-failed", {
        method: "POST",
        body: JSON.stringify({
          broadcast_ids: selected,
          dry_run: false,
          idempotency_key: retryModal.key,
        }),
      });
      setRetryModal(null);
      setSelected([]);
      await state.reload();
      push(
        result.replayed
          ? "Операция уже выполнялась; показан сохранённый результат."
          : `В очередь возвращено рассылок: ${result.eligible_broadcasts}.`,
        "success",
      );
    } catch (cause) {
      push(cause instanceof Error ? cause.message : String(cause), "error");
    } finally {
      setBusy(false);
    }
  }

  function toggle(id: string, checked: boolean) {
    setSelected((current) => checked ? [...current, id] : current.filter((item) => item !== id));
  }

  return <section className="page broadcasts-workbench">
    <Header
      title="Ручные рассылки"
      description="Текст, фото, кнопка, расписание и безопасное восстановление failed-отправок."
      action={<button className="with-icon" onClick={state.reload}><Icon name="refresh"/>Обновить</button>}
    />
    {state.error && <ErrorBox text={state.error}/>} 
    <div className="columns broadcasts-layout">
      <form className="panel form broadcast-create" onSubmit={create} aria-label="Новая рассылка">
        <h3>Новая рассылка</h3>
        <Field label="Аудитория"><select name="audience_type"><option value="all">Все</option><option value="active_vip">Активные VIP</option><option value="vip_grace">VIP + Grace</option><option value="standard">Standard</option><option value="title_followers">Подписчики тайтла</option></select></Field>
        <Field label="UUID тайтла"><input name="title_id" placeholder="Только для подписчиков тайтла"/></Field>
        <Field label="Текст"><textarea name="text" rows={7} maxLength={1024} required/></Field>
        <div className="row"><Field label="Текст кнопки"><input name="button_text" maxLength={64}/></Field><Field label="URL"><input name="button_url" type="url"/></Field></div>
        <Field label="Дата отправки"><input name="scheduled_at" type="datetime-local"/></Field>
        <label className="checkbox"><input name="send_now" type="checkbox"/> Отправить сразу</label>
        <button className="primary" disabled={busy}>{busy ? "Сохранение…" : "Создать"}</button>
        <label className={`upload${created ? "" : " disabled"}`}>Фото к текущей рассылке<input disabled={!created} hidden type="file" accept="image/*" onChange={(event) => event.target.files?.[0] && uploadPhoto(event.target.files[0])}/></label>
        {created && <small className="broadcast-created">Текущая рассылка: <code>{created}</code></small>}
      </form>
      <div className="panel broadcast-list-panel">
        <div className="broadcast-list-head"><div><h3>Последние рассылки</h3><p>Failed-записи выбираются для обязательного dry-run.</p></div><div><select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Фильтр статуса"><option value="all">Все статусы</option><option value="draft">Черновик</option><option value="scheduled">Запланировано</option><option value="processing">Выполняется</option><option value="completed">Завершено</option><option value="failed">Ошибка</option><option value="cancelled">Отменено</option></select><button disabled={!selected.length || busy} onClick={previewRetry}>Dry-run retry ({selected.length})</button></div></div>
        {state.loading ? <Loading label="Загружаем рассылки…"/> : items.length ? <div className="cards compact broadcast-cards">{items.map((item) => <article key={item.id} className={selected.includes(item.id) ? "selected" : ""}><label className="broadcast-select"><input type="checkbox" disabled={item.status !== "failed"} checked={selected.includes(item.id)} onChange={(event) => toggle(item.id, event.target.checked)}/><span className="sr-only">Выбрать failed-рассылку</span></label><div className="broadcast-card-main"><div className="item-head"><strong>{item.text.slice(0, 140)}</strong><Badge value={item.status}/></div><small>{item.sent_count}/{item.total_count}, ошибок {item.failed_count}, пропущено {item.skipped_count} · {date(item.created_at)}</small><code>{item.id}</code></div></article>)}</div> : <div className="empty-state"><Icon name="send" size={30}/><strong>Рассылок не найдено</strong><span>Измените фильтр или создайте новую рассылку.</span></div>}
      </div>
    </div>
    {retryModal && <div className="admin-modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setRetryModal(null)}><section className="admin-modal" role="dialog" aria-modal="true" aria-labelledby="retry-title"><header><div><h2 id="retry-title">Dry-run массового retry</h2><p>Кандидаты повторно рассчитываются под advisory lock перед записью.</p></div><button aria-label="Закрыть" onClick={() => setRetryModal(null)}>×</button></header><dl className="retry-summary"><div><dt>Запрошено</dt><dd>{retryModal.preview.requested}</dd></div><div><dt>Найдено failed</dt><dd>{retryModal.preview.found}</dd></div><div><dt>Доступно рассылок</dt><dd>{retryModal.preview.eligible_broadcasts}</dd></div><div><dt>Получателей</dt><dd>{retryModal.preview.retriable_recipients}</dd></div></dl><div className="retry-items">{retryModal.preview.items.map((item) => <div key={item.id}><code>{item.id}</code><span>{item.recipients} получателей</span></div>)}</div><footer><button onClick={() => setRetryModal(null)}>Отмена</button><button className="primary" disabled={!retryModal.preview.eligible_broadcasts || busy} onClick={executeRetry}>{busy ? "Выполняется…" : "Подтвердить retry"}</button></footer></section></div>}
  </section>;
}
