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
      <label>Зачем выполняется действие<textarea name="reason" rows={4} minLength={3} maxLength={1000} required autoFocus placeholder="Коротко опишите причину"/></label>
      <p className="catalog-action-warning">Текущее состояние сохранится в журнале и истории изменений. При необходимости его можно восстановить.</p>
      <footer><button type="button" onClick={onClose}>Отмена</button><button className={action.danger ? "danger-soft" : "primary"} disabled={busy}>{busy ? "Выполняется…" : action.confirmLabel}</button></footer>
    </form>
  </DialogShell>;
}

export function EditTitleDialog({ item, onClose, onSubmit }:{ item:Title; onClose:()=>void; onSubmit:(event:FormEvent<HTMLFormElement>)=>void }) {
  return <DialogShell title="Редактирование произведения" description="Если данные изменились в другой вкладке, система не перезапишет их устаревшей версией." onClose={onClose}><form className="catalog-form" onSubmit={onSubmit}>
    <label>Адрес страницы<input name="slug" defaultValue={item.slug} required pattern="[a-z0-9]+(?:-[a-z0-9]+)*"/><small>Служебная часть ссылки. Обычно менять её не нужно.</small></label>
    <div className="row"><label>Название в каталоге<input name="english_title" defaultValue={item.english_title} required/></label><label>Оригинальное название<input name="original_title" defaultValue={item.original_title} required/></label></div>
    <div className="row"><label>Язык оригинала<input name="original_language" defaultValue={item.original_language} required/></label><label>Состояние перевода<select name="publication_status" defaultValue={item.publication_status}><option value="ongoing">Перевод продолжается</option><option value="completed">Перевод завершён</option><option value="hiatus">Перевод на паузе</option></select></label></div>
    <label>Другие названия<textarea name="aliases" rows={5} defaultValue={item.aliases.join("\n")} placeholder="По одному названию на строку"/></label>
    <label>Ссылка на Boosty<input name="boosty_url" type="url" defaultValue={item.boosty_url || ""}/></label>
    <label>Описание<textarea name="description" rows={7} defaultValue={item.description}/></label>
    <label>Причина изменения<input name="reason" required minLength={3} placeholder="Например: исправлено название"/></label>
    <footer><button type="button" onClick={onClose}>Отмена</button><button className="primary">Сохранить</button></footer>
  </form></DialogShell>;
}

export function CreateReleaseDialog({ title, onClose, onSubmit }:{ title:Title; onClose:()=>void; onSubmit:(event:FormEvent<HTMLFormElement>)=>void }) {
  return <DialogShell title={`Добавить пакет · ${title.english_title}`} description="Укажите главы. После создания загрузите PDF и EPUB — система проверит их автоматически." onClose={onClose}><form className="catalog-form" onSubmit={onSubmit}>
    <div className="row"><label>Первая глава<input name="chapter_start" type="number" min="0" required/></label><label>Последняя глава<input name="chapter_end" type="number" min="0" required/></label></div>
    <label>Название пакета<input name="display_name" placeholder="Можно оставить пустым"/></label>
    <label>Ссылка на публикацию Boosty<input name="boosty_url" type="url"/></label>
    <footer><button type="button" onClick={onClose}>Отмена</button><button className="primary">Создать пакет</button></footer>
  </form></DialogShell>;
}

export function EditReleaseDialog({ item, onClose, onSubmit }:{ item:Release; onClose:()=>void; onSubmit:(event:FormEvent<HTMLFormElement>)=>void }) {
  return <DialogShell title="Редактирование пакета глав" description="После изменения диапазона PDF и EPUB будут проверены повторно." onClose={onClose}><form className="catalog-form" onSubmit={onSubmit}>
    <div className="row"><label>Первая глава<input name="chapter_start" type="number" min="0" defaultValue={item.chapter_start} required/></label><label>Последняя глава<input name="chapter_end" type="number" min="0" defaultValue={item.chapter_end} required/></label></div>
    <label>Название пакета<input name="display_name" defaultValue={item.display_name || ""}/></label>
    <label>Ссылка на публикацию Boosty<input name="boosty_url" type="url" defaultValue={item.boosty_url || ""}/></label>
    <label className="catalog-checkbox"><input name="comments_enabled" type="checkbox" defaultChecked={item.comments_enabled}/>Разрешить комментарии к пакету</label>
    <label>Причина изменения<input name="reason" required minLength={3}/></label>
    <footer><button type="button" onClick={onClose}>Отмена</button><button className="primary">Сохранить</button></footer>
  </form></DialogShell>;
}

export function PreviewDialog({ title, data, onClose }:{ title:string; data:Preview; onClose:()=>void }) {
  return <DialogShell title={`Предпросмотр · ${title}`} description="Это только проверка. Сообщения ещё не отправляются." onClose={onClose}>{data.warnings.length > 0 && <div className="notice" role="status">{data.warnings.join(" · ")}</div>}<div className="catalog-preview-grid"><article><h3>Сообщение в боте</h3><pre>{data.bot_html}</pre></article><article><h3>Публикация в канале</h3><pre>{data.channel_html}</pre></article></div></DialogShell>;
}

export function CleanupDialog({ data, busy, onClose, onExecute }:{ data:CleanupPreview; busy:boolean; onClose:()=>void; onExecute:()=>void }) {
  return <DialogShell title="Неиспользуемые версии файлов" description="Перед удалением список будет проверен ещё раз." onClose={onClose}><div className="catalog-cleanup-summary"><strong>{data.candidate_count} версий</strong><span>{bytes(data.bytes)}</span><code>{data.confirmation}</code></div><div className="catalog-cleanup-list">{data.items.map((item) => <div key={item.id}><span>{item.filename} · версия {item.version}</span><small>{bytes(item.size_bytes)} · {date(item.created_at)}</small></div>)}</div><footer className="catalog-modal-footer"><button onClick={onClose}>Отмена</button><button className="danger-soft" disabled={!data.candidate_count || busy} onClick={onExecute}>{busy ? "Удаление…" : "Удалить после повторной проверки"}</button></footer></DialogShell>;
}
