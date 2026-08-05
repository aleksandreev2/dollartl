import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { api, confirmAction } from "./api";
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

type Page<T> = {
  page: number;
  page_size: number;
  total: number;
  pages: number;
  items: T[];
  categories?: string[];
};
type CommentRow = {
  id: string;
  user_id: string;
  anonymous_id: number;
  telegram_id: number;
  telegram_username?: string | null;
  target_type: string;
  public_body: string;
  original_body: string;
  replacement_count: number;
  vip_snapshot: boolean;
  is_deleted: boolean;
  created_at: string;
};
type RatingRow = {
  id: string;
  user_id: string;
  anonymous_id: number;
  telegram_id: number;
  telegram_username?: string | null;
  title: string;
  release_label: string;
  score: number;
  feedback: string;
  status: string;
  vip_snapshot: boolean;
  created_at: string;
};
type ReportRow = {
  id: string;
  user_id: string;
  anonymous_id: number;
  telegram_id: number;
  telegram_username?: string | null;
  target_type: string;
  category: string;
  status: string;
  description: string;
  assigned_admin_id?: number | null;
  created_at: string;
};
type BatchPreview = {
  dry_run: boolean;
  replayed: boolean;
  kind: string;
  action: string;
  requested: number;
  found: number;
  missing: number;
  changed?: number;
};

function Modal({
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
      onMouseDown={(event: React.MouseEvent<HTMLDivElement>) =>
        event.target === event.currentTarget && onClose()
      }
    >
      <section className={`action-modal${wide ? " wide" : ""}`} role="dialog" aria-modal="true">
        <header><strong>{title}</strong><button onClick={onClose}>×</button></header>
        <div className="action-modal-body">{children}</div>
      </section>
    </div>
  );
}

function BatchModal({
  kind,
  ids,
  onClose,
  onDone,
}: {
  kind: "comments" | "ratings" | "reports";
  ids: string[];
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const actions = kind === "comments"
    ? [["delete", "Удалить"], ["restore", "Восстановить"]]
    : kind === "ratings"
      ? [["reviewed", "Проверено"], ["in_progress", "В работе"], ["fixed", "Исправлено"], ["dismissed", "Отклонено"]]
      : [["in_progress", "В работу"], ["resolved", "Решить"], ["rejected", "Отклонить"], ["open", "Вернуть в открытые"]];
  const [action, setAction] = useState(actions[0][0]);
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState<BatchPreview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const idempotency = useMemo(
    () => `admin-${kind}-${crypto.randomUUID()}`,
    [kind, ids.join(",")],
  );

  async function run(dryRun: boolean) {
    setBusy(true);
    setError("");
    try {
      const result = await api<BatchPreview>("/moderation/batch", {
        method: "POST",
        body: JSON.stringify({
          kind,
          ids,
          action,
          note: note || null,
          dry_run: dryRun,
          idempotency_key: idempotency,
        }),
      });
      if (dryRun) setPreview(result);
      else await onDone();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => setPreview(null), [action, note]);
  return (
    <Modal title={`Массовое действие · ${ids.length} элементов`} onClose={onClose}>
      {error && <ErrorBox text={error}/>} 
      <div className="form">
        <Field label="Действие">
          <select value={action} onChange={(event: React.ChangeEvent<HTMLSelectElement>) => setAction(event.target.value)}>
            {actions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </Field>
        <Field label="Заметка для аудита"><textarea value={note} onChange={(event: React.ChangeEvent<HTMLTextAreaElement>) => setNote(event.target.value)} rows={4}/></Field>
        {preview && (
          <div className="batch-preview">
            <strong>Dry-run завершён</strong>
            <span>Запрошено: {preview.requested}</span>
            <span>Найдено: {preview.found}</span>
            <span>Пропущено: {preview.missing}</span>
            <small>Для массовых жалоб ответ пользователю не отправляется. Индивидуальный ответ доступен в карточке жалобы.</small>
          </div>
        )}
        <div className="modal-actions">
          <button onClick={onClose}>Отмена</button>
          {!preview ? (
            <button className="primary" disabled={busy} onClick={() => run(true)}>{busy ? "Проверяем…" : "Проверить dry-run"}</button>
          ) : (
            <button className="danger" disabled={busy || !preview.found} onClick={() => run(false)}>{busy ? "Применяем…" : "Подтвердить выполнение"}</button>
          )}
        </div>
      </div>
    </Modal>
  );
}

function RatingModal({
  item,
  onClose,
  onDone,
}: {
  item: RatingRow;
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api(`/ratings/${item.id}/workflow`, {
        method: "POST",
        body: JSON.stringify({
          status: form.get("status"),
          note: form.get("note") || null,
        }),
      });
      await onDone();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }
  return (
    <Modal title={`Оценка ${item.score}/5 · ${item.title}`} onClose={onClose}>
      {error && <ErrorBox text={error}/>} 
      <p className="modal-quote">{item.feedback}</p>
      <form className="form" onSubmit={submit}>
        <Field label="Новый статус"><select name="status" defaultValue={item.status}><option value="new">Новая</option><option value="reviewed">Проверено</option><option value="in_progress">В работе</option><option value="fixed">Исправлено</option><option value="dismissed">Отклонено</option></select></Field>
        <Field label="Заметка"><textarea name="note" rows={4}/></Field>
        <div className="modal-actions"><button type="button" onClick={onClose}>Отмена</button><button className="primary">Сохранить</button></div>
      </form>
    </Modal>
  );
}

function ReportModal({
  item,
  onClose,
  onDone,
}: {
  item: ReportRow;
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api(`/reports/${item.id}`, {
        method: "POST",
        body: JSON.stringify({
          status: form.get("status"),
          reply: form.get("reply") || null,
        }),
      });
      await onDone();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }
  return (
    <Modal title={`Жалоба · ${item.category}`} onClose={onClose}>
      {error && <ErrorBox text={error}/>} 
      <p className="modal-quote">{item.description}</p>
      <form className="form" onSubmit={submit}>
        <Field label="Новый статус"><select name="status" defaultValue={item.status}><option value="open">Открыта</option><option value="in_progress">В работе</option><option value="resolved">Решена</option><option value="rejected">Отклонена</option></select></Field>
        <Field label="Ответ пользователю"><textarea name="reply" rows={5} placeholder="Необязательно. При заполнении бот отправит сообщение пользователю."/></Field>
        <div className="modal-actions"><button type="button" onClick={onClose}>Отмена</button><button className="primary">Сохранить и отправить ответ</button></div>
      </form>
    </Modal>
  );
}

export function CommunityWorkbenchView() {
  const [tab, setTab] = useState<"comments" | "ratings" | "reports">("comments");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("active");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string[]>([]);
  const [batchOpen, setBatchOpen] = useState(false);
  const [ratingOpen, setRatingOpen] = useState<RatingRow | null>(null);
  const [reportOpen, setReportOpen] = useState<ReportRow | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    setPage(1);
    setSelected([]);
    setStatus(tab === "comments" ? "active" : tab === "ratings" ? "new" : "open");
  }, [tab]);
  useEffect(() => {
    setPage(1);
    setSelected([]);
  }, [query, status]);

  const current = useData(async () => {
    if (tab === "comments") {
      return {
        kind: "comments" as const,
        page: await api<Page<CommentRow>>(`/moderation/comments?q=${encodeURIComponent(query)}&state=${status}&page=${page}&page_size=30`),
      };
    }
    if (tab === "ratings") {
      return {
        kind: "ratings" as const,
        page: await api<Page<RatingRow>>(`/moderation/ratings?q=${encodeURIComponent(query)}&status=${status}&page=${page}&page_size=30`),
      };
    }
    return {
      kind: "reports" as const,
      page: await api<Page<ReportRow>>(`/moderation/reports?q=${encodeURIComponent(query)}&status=${status}&page=${page}&page_size=30`),
    };
  }, [tab, query, status, page]);

  const pageData = current.data?.page;
  const items = pageData?.items || [];
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const allSelected = items.length > 0 && items.every((item) => selectedSet.has(item.id));
  function toggle(id: string) {
    setSelected((value) => value.includes(id)
      ? value.filter((item) => item !== id)
      : [...value, id]);
  }
  function toggleAll() {
    const ids = items.map((item) => item.id);
    setSelected(allSelected ? [] : ids);
  }
  async function moderateComment(item: CommentRow) {
    if (!(await confirmAction(item.is_deleted ? "Восстановить комментарий?" : "Удалить комментарий?"))) return;
    await api(`/comments/${item.id}/moderate`, {
      method: "POST",
      body: JSON.stringify({ deleted: !item.is_deleted }),
    });
    await current.reload();
  }
  async function reloadCurrent() {
    await current.reload();
    setSelected([]);
    setBatchOpen(false);
    setRatingOpen(null);
    setReportOpen(null);
    setNotice("Изменения применены и записаны в аудит.");
  }
  const statusOptions = tab === "comments"
    ? [["active", "Активные"], ["deleted", "Удалённые"], ["all", "Все"]]
    : tab === "ratings"
      ? [["new", "Новые"], ["reviewed", "Проверенные"], ["in_progress", "В работе"], ["fixed", "Исправленные"], ["dismissed", "Отклонённые"], ["all", "Все"]]
      : [["open", "Открытые"], ["in_progress", "В работе"], ["resolved", "Решённые"], ["rejected", "Отклонённые"], ["all", "Все"]];

  return (
    <section className="page moderation-page">
      <Header
        title="Сообщество"
        description="Постмодерация, рабочие статусы и безопасные массовые действия."
        action={<button className="with-icon" onClick={current.reload}><Icon name="refresh"/>Обновить</button>}
      />
      {notice && <Notice text={notice}/>} 
      {current.error && <ErrorBox text={current.error}/>} 
      <div className="tabs">
        <button className={tab === "comments" ? "active" : ""} onClick={() => setTab("comments")}>Комментарии</button>
        <button className={tab === "ratings" ? "active" : ""} onClick={() => setTab("ratings")}>Оценки</button>
        <button className={tab === "reports" ? "active" : ""} onClick={() => setTab("reports")}>Жалобы</button>
      </div>
      <div className="toolbar">
        <label className="toolbar-search"><Icon name="search"/><input value={query} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)} placeholder="Текст, username или Anonymous ID"/></label>
        <select value={status} onChange={(event: React.ChangeEvent<HTMLSelectElement>) => setStatus(event.target.value)}>{statusOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        {selected.length > 0 && <button className="primary" onClick={() => setBatchOpen(true)}>Массовое действие · {selected.length}</button>}
      </div>
      {current.loading || !current.data ? <Loading/> : (
        <div className="work-table moderation-table">
          <table>
            <thead><tr><th><input type="checkbox" checked={allSelected} onChange={toggleAll}/></th><th>Пользователь</th><th>Содержание</th><th>Статус</th><th>Дата</th><th/></tr></thead>
            <tbody>
              {current.data.kind === "comments" && current.data.page.items.map((item) => <tr key={item.id} className={selectedSet.has(item.id) ? "selected" : ""}><td><input type="checkbox" checked={selectedSet.has(item.id)} onChange={() => toggle(item.id)}/></td><td><strong>Anonymous {item.anonymous_id}</strong><small>{item.telegram_username ? `@${item.telegram_username}` : item.telegram_id}</small></td><td><p>{item.public_body}</p><small>{item.replacement_count ? `Автозамен: ${item.replacement_count}` : item.target_type}</small></td><td><Badge value={item.is_deleted ? "cancelled" : "completed"}/></td><td>{date(item.created_at)}</td><td><button onClick={() => moderateComment(item)}>{item.is_deleted ? "Восстановить" : "Удалить"}</button></td></tr>)}
              {current.data.kind === "ratings" && current.data.page.items.map((item) => <tr key={item.id} className={selectedSet.has(item.id) ? "selected" : ""}><td><input type="checkbox" checked={selectedSet.has(item.id)} onChange={() => toggle(item.id)}/></td><td><strong>Anonymous {item.anonymous_id}</strong><small>{item.telegram_username ? `@${item.telegram_username}` : item.telegram_id}</small></td><td><strong>{item.score}/5 · {item.title}</strong><p>{item.feedback}</p><small>{item.release_label}</small></td><td><Badge value={item.status}/></td><td>{date(item.created_at)}</td><td><button onClick={() => setRatingOpen(item)}>Открыть</button></td></tr>)}
              {current.data.kind === "reports" && current.data.page.items.map((item) => <tr key={item.id} className={selectedSet.has(item.id) ? "selected" : ""}><td><input type="checkbox" checked={selectedSet.has(item.id)} onChange={() => toggle(item.id)}/></td><td><strong>Anonymous {item.anonymous_id}</strong><small>{item.telegram_username ? `@${item.telegram_username}` : item.telegram_id}</small></td><td><strong>{item.category}</strong><p>{item.description}</p><small>{item.target_type}</small></td><td><Badge value={item.status}/></td><td>{date(item.created_at)}</td><td><button onClick={() => setReportOpen(item)}>Открыть</button></td></tr>)}
            </tbody>
          </table>
        </div>
      )}
      {pageData && <div className="pager"><button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Назад</button><span>Страница {pageData.page} из {pageData.pages} · {pageData.total} записей</span><button disabled={page >= pageData.pages} onClick={() => setPage((value) => value + 1)}>Дальше</button></div>}
      {batchOpen && <BatchModal kind={tab} ids={selected} onClose={() => setBatchOpen(false)} onDone={reloadCurrent}/>} 
      {ratingOpen && <RatingModal item={ratingOpen} onClose={() => setRatingOpen(null)} onDone={reloadCurrent}/>} 
      {reportOpen && <ReportModal item={reportOpen} onClose={() => setReportOpen(null)} onDone={reloadCurrent}/>} 
    </section>
  );
}
