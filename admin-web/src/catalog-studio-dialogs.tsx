import React, { FormEvent, useEffect, useRef } from "react";
import { bytes, date } from "./admin-ui";
import type { CleanupPreview, Preview, ReasonAction, Release, Title } from "./catalog-studio-types";

export function DialogShell({ title, description, onClose, children }:{
  title: string;
  description?: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const closeRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return <div className="catalog-modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <section className="catalog-modal" role="dialog" aria-modal="true" aria-labelledby="catalog-dialog-title">
      <header><div><h2 id="catalog-dialog-title">{title}</h2>{description && <p>{description}</p>}</div><button ref={closeRef} type="button" aria-label="Закрыть" onClick={onClose}>×</button></header>
      {children}
    </section>
  </div>;
}

export function ReasonDialog({ action, busy, onClose, onSubmit }:{
  action: ReasonAction;
  busy: boolean;
  onClose: () => void;
  onSubmit: (reason: string) => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const reason = String(new FormData(event.currentTarget).get("reason") || "").trim();
    if (reason.length >= 3) onSubmit(reason);
  }
  return <DialogShell title={action.title} description={action.description} onClose={onClose}>
    <form className="catalog-form" onSubmit={submit}>
      <label>Причина операции<textarea name="reason" rows={4} minLength={3} maxLength={1000} required autoFocus placeholder="Что меняется и почему"/></label>
      <p className="catalog-action-warning">Текущее состояние сначала сохраняется в audit и истории версий. Операцию можно проверить и восстановить.</p>
      <footer><button type="button" onClick={onClose}>Отмена</button><button className={action.danger ? "danger-soft" : "primary"} disabled={busy}>{busy ? "Выполняется…" : action.confirmLabel}</button></footer>
    </form>
  </DialogShell>;
}

export function CreateTitleDialog({ onClose, onSubmit }:{ onClose:()=>void; onSubmit:(event:FormEvent<HTMLFormElement>)=>void }) {
  return <DialogShell title="Новый тайтл" description="Создание черновика каталога." onClose={onClose}><form className="catalog-form" onSubmit={onSubmit}><div className="row"><label>Английское название<input name="english_title" required/></label><label>Оригинальное название<input name="original_title" required/></label></div><div className="row"><label>Язык<input name="original_language" required/></label><label>Статус<select name="publication_status" defaultValue="ongoing"><option value="ongoing">Продолжается</option><option value="completed">Завершён</option><option value="hiatus">Пауза</option></select></label></div><label>Aliases<textarea name="aliases" rows={4}/></label><label>Boosty URL<input name="boosty_url" type="url"/></label><label>Описание<textarea name="description" rows={7}/></label><footer><button type="button" onClick={onClose}>Отмена</button><button className="primary">Создать</button></footer></form></DialogShell>;
}

export function EditTitleDialog({ item, onClose, onSubmit }:{ item:Title; onClose:()=>void; onSubmit:(event:FormEvent<HTMLFormElement>)=>void }) {
  return <DialogShell title="Редактирование тайтла" description="Сохранение защищено optimistic conflict detection." onClose={onClose}><form className="catalog-form" onSubmit={onSubmit}><label>Slug<input name="slug" defaultValue={item.slug} required pattern="[a-z0-9]+(?:-[a-z0-9]+)*"/></label><div className="row"><label>Английское<input name="english_title" defaultValue={item.english_title} required/></label><label>Оригинальное<input name="original_title" defaultValue={item.original_title} required/></label></div><div className="row"><label>Язык<input name="original_language" defaultValue={item.original_language} required/></label><label>Статус<select name="publication_status" defaultValue={item.publication_status}><option value="ongoing">Продолжается</option><option value="completed">Завершён</option><option value="hiatus">Пауза</option></select></label></div><label>Aliases<textarea name="aliases" rows={5} defaultValue={item.aliases.join("\n")}/></label><label>Boosty URL<input name="boosty_url" type="url" defaultValue={item.boosty_url || ""}/></label><label>Описание<textarea name="description" rows={7} defaultValue={item.description}/></label><label>Причина<input name="reason" required minLength={3}/></label><footer><button type="button" onClick={onClose}>Отмена</button><button className="primary">Сохранить</button></footer></form></DialogShell>;
}

export function CreateReleaseDialog({ title, onClose, onSubmit }:{ title:Title; onClose:()=>void; onSubmit:(event:FormEvent<HTMLFormElement>)=>void }) {
  return <DialogShell title={`Новый пакет · ${title.english_title}`} description="Диапазон проверяется на пересечения." onClose={onClose}><form className="catalog-form" onSubmit={onSubmit}><div className="row"><label>С главы<input name="chapter_start" type="number" min="0" required/></label><label>По главу<input name="chapter_end" type="number" min="0" required/></label></div><label>Название<input name="display_name"/></label><label>Boosty URL<input name="boosty_url" type="url"/></label><footer><button type="button" onClick={onClose}>Отмена</button><button className="primary">Создать</button></footer></form></DialogShell>;
}

export function EditReleaseDialog({ item, onClose, onSubmit }:{ item:Release; onClose:()=>void; onSubmit:(event:FormEvent<HTMLFormElement>)=>void }) {
  return <DialogShell title="Редактирование пакета" description="После изменения диапазона файлы проверяются повторно." onClose={onClose}><form className="catalog-form" onSubmit={onSubmit}><div className="row"><label>С главы<input name="chapter_start" type="number" min="0" defaultValue={item.chapter_start} required/></label><label>По главу<input name="chapter_end" type="number" min="0" defaultValue={item.chapter_end} required/></label></div><label>Название<input name="display_name" defaultValue={item.display_name || ""}/></label><label>Boosty URL<input name="boosty_url" type="url" defaultValue={item.boosty_url || ""}/></label><label className="catalog-checkbox"><input name="comments_enabled" type="checkbox" defaultChecked={item.comments_enabled}/>Комментарии включены</label><label>Причина<input name="reason" required minLength={3}/></label><footer><button type="button" onClick={onClose}>Отмена</button><button className="primary">Сохранить</button></footer></form></DialogShell>;
}

export function PreviewDialog({ title, data, onClose }:{ title:string; data:Preview; onClose:()=>void }) {
  return <DialogShell title={`Preview · ${title}`} description="Предпросмотр ничего не публикует." onClose={onClose}>{data.warnings.length > 0 && <div className="notice" role="status">{data.warnings.join(" · ")}</div>}<div className="catalog-preview-grid"><article><h3>Telegram bot</h3><pre>{data.bot_html}</pre></article><article><h3>Telegram channel</h3><pre>{data.channel_html}</pre></article></div></DialogShell>;
}

export function CleanupDialog({ data, busy, onClose, onExecute }:{ data:CleanupPreview; busy:boolean; onClose:()=>void; onExecute:()=>void }) {
  return <DialogShell title="Очистка неактивных файлов" description="Перед удалением кандидаты будут рассчитаны повторно." onClose={onClose}><div className="catalog-cleanup-summary"><strong>{data.candidate_count} версий</strong><span>{bytes(data.bytes)}</span><code>{data.confirmation}</code></div><div className="catalog-cleanup-list">{data.items.map((item) => <div key={item.id}><span>{item.filename} · v{item.version}</span><small>{bytes(item.size_bytes)} · {date(item.created_at)}</small></div>)}</div><footer className="catalog-modal-footer"><button onClick={onClose}>Отмена</button><button className="danger-soft" disabled={!data.candidate_count || busy} onClick={onExecute}>{busy ? "Удаление…" : "Удалить после повторной проверки"}</button></footer></DialogShell>;
}
