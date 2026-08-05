import React, { FormEvent, useState } from "react";
import { api } from "./api";
import type { SuggestionItem, TitleItem } from "./types";
import {
  Badge,
  ErrorBox,
  Field,
  Header,
  Icon,
  Loading,
  Notice,
  bytes,
  date,
  useData,
} from "./admin-ui";

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
        <header><strong>{title}</strong><button aria-label="Закрыть" onClick={onClose}>×</button></header>
        <div className="action-modal-body">{children}</div>
      </section>
    </div>
  );
}

function SuggestionDecisionModal({
  item,
  onClose,
  onDone,
}: {
  item: SuggestionItem;
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const titles = useData(() => api<TitleItem[]>("/titles?limit=500"), []);
  const [status, setStatus] = useState("accepted");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      await api(`/suggestions/${item.id}/decision`, {
        method: "POST",
        body: JSON.stringify({
          status,
          public_reason: form.get("public_reason") || null,
          internal_note: form.get("internal_note") || null,
          linked_title_id: status === "translated"
            ? form.get("linked_title_id") || null
            : null,
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
    <Modal title={`Решение по заявке · ${item.original_title || "Без названия"}`} onClose={onClose} wide>
      <form className="form" onSubmit={submit}>
        {error && <ErrorBox text={error}/>} 
        <div className="decision-status">
          <button type="button" className={status === "accepted" ? "active" : ""} onClick={() => setStatus("accepted")}>Принять</button>
          <button type="button" className={status === "rejected" ? "active danger" : ""} onClick={() => setStatus("rejected")}>Отклонить</button>
          <button type="button" className={status === "translated" ? "active primary" : ""} onClick={() => setStatus("translated")}>Переведено</button>
        </div>
        {status === "translated" && (
          <Field label="Связанный опубликованный тайтл">
            <select name="linked_title_id" required>
              <option value="">Выберите тайтл</option>
              {titles.data?.map((title) => (
                <option key={title.id} value={title.id}>{title.english_title} · {title.original_title}</option>
              ))}
            </select>
          </Field>
        )}
        <Field label={status === "rejected" ? "Публичная причина отказа" : "Публичный комментарий пользователю"}>
          <textarea name="public_reason" rows={4} required={status === "rejected"}/>
        </Field>
        <Field label="Внутренняя заметка"><textarea name="internal_note" rows={4}/></Field>
        <div className="modal-actions">
          <button type="button" onClick={onClose}>Отмена</button>
          <button className="primary" disabled={busy}>{busy ? "Сохраняем…" : "Применить и уведомить"}</button>
        </div>
      </form>
    </Modal>
  );
}

export function SuggestionsWorkbenchView() {
  const [filter, setFilter] = useState("under_review");
  const state = useData(
    () => api<SuggestionItem[]>(`/suggestions?status=${filter}&limit=500`),
    [filter],
  );
  const [decision, setDecision] = useState<SuggestionItem | null>(null);
  const [notice, setNotice] = useState("");

  return (
    <section className="page">
      <Header
        title="Предложения тайтлов"
        description="Проверка raw-файлов и решения без системных prompt-окон."
        action={<button className="with-icon" onClick={state.reload}><Icon name="refresh"/>Обновить</button>}
      />
      {notice && <Notice text={notice}/>} 
      {state.error && <ErrorBox text={state.error}/>} 
      <div className="toolbar">
        <select value={filter} onChange={(event: React.ChangeEvent<HTMLSelectElement>) => setFilter(event.target.value)}>
          <option value="under_review">На проверке</option><option value="accepted">Принятые</option><option value="translated">Переведённые</option><option value="rejected">Отклонённые</option><option value="all">Все</option>
        </select>
      </div>
      {state.loading ? <Loading/> : (
        <div className="cards suggestion-cards">
          {state.data?.map((item) => (
            <article key={item.id}>
              <div className="item-head"><strong>{item.original_title || "Без названия"}</strong><Badge value={item.status}/></div>
              <div className="suggestion-meta"><span>Язык: <b>{item.detected_language || "—"}</b></span><span>Глав: <b>{item.chapter_count || "—"}</b></span><span>Scope: <b>1–{item.requested_chapter_end || "—"}</b></span></div>
              <p><b>Raw:</b> {item.raw_file ? `${item.raw_file.filename} · ${bytes(item.raw_file.size_bytes)} · ${item.raw_file.validation_status}` : "ОТСУТСТВУЕТ"}</p>
              {item.duplicate_review_required && <Notice text="Нужна ручная проверка возможного дубля"/>}
              <small>Anonymous {item.user.anonymous_id} · Telegram {item.user.telegram_id} · {date(item.submitted_at)}</small>
              {item.status === "under_review" && <div className="actions"><button className="primary" onClick={() => setDecision(item)}>Принять решение</button></div>}
            </article>
          ))}
        </div>
      )}
      {decision && (
        <SuggestionDecisionModal
          item={decision}
          onClose={() => setDecision(null)}
          onDone={async () => {
            setDecision(null);
            await state.reload();
            setNotice("Решение сохранено, пользователь уведомлён.");
          }}
        />
      )}
    </section>
  );
}
