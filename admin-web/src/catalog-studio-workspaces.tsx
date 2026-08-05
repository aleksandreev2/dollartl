import React from "react";
import { Badge, Icon, Loading, bytes, date } from "./admin-ui";
import type { DataState, FileVersion, Release, ReleaseDetail, Revision, TitleDetail } from "./catalog-studio-types";

function translationStatus(value: string) {
  if (value === "ongoing") return "Перевод продолжается";
  if (value === "completed") return "Перевод завершён";
  if (value === "hiatus") return "Перевод на паузе";
  return value;
}

export function TitleWorkspace({ data, onEdit, onPreview, onCover, onPublication, onNewRelease, onOpenRelease, onRollback }:{
  data: TitleDetail;
  onEdit:()=>void;
  onPreview:()=>void;
  onCover:(file:File)=>void;
  onPublication:()=>void;
  onNewRelease:()=>void;
  onOpenRelease:(id:string)=>void;
  onRollback:(revision:Revision)=>void;
}) {
  const title = data.title;
  return <>
    <div className="catalog-title-hero">
      {data.cover_url ? <img src={data.cover_url} alt={`Обложка ${title.english_title}`}/> : <div className="catalog-cover-empty"><Icon name="book" size={30}/></div>}
      <div><div className="catalog-title-state"><Badge value={title.is_published ? "completed" : "draft"}/><span>Адрес: /{title.slug}</span></div><h2>{title.english_title}</h2><p>{title.original_title}</p><small>{title.aliases.join(" · ")}</small></div>
    </div>
    <div className="catalog-actions"><button onClick={onEdit}>Изменить данные</button><button onClick={onPreview}>Предпросмотр</button><label>Заменить обложку<input hidden type="file" accept="image/*" onChange={(event) => event.target.files?.[0] && onCover(event.target.files[0])}/></label><button className={title.is_published ? "danger-soft" : "primary"} onClick={onPublication}>{title.is_published ? "Снять с публикации" : "Опубликовать"}</button></div>
    <div className="catalog-description"><h3>Описание</h3><p>{title.description || "Описание ещё не добавлено."}</p><dl><dt>Перевод</dt><dd>{translationStatus(title.publication_status)}</dd><dt>Доступно</dt><dd>до {title.latest_chapter} главы</dd><dt>Boosty</dt><dd>{title.boosty_url || "Ссылка не добавлена"}</dd></dl></div>
    <div className="catalog-section-head"><div><h3>Пакеты глав</h3><p>Файлы, проверка и публикация отдельных диапазонов.</p></div><button onClick={onNewRelease}>Добавить пакет</button></div>
    <div className="catalog-release-grid">{data.releases.length ? data.releases.map((item) => <button key={item.id} onClick={() => onOpenRelease(item.id)}><div><strong>{item.display_name || item.chapter_label}</strong><small>{item.validation_message || "Файлы ещё не проверены"}</small></div><div><Badge value={item.validation_status}/><span>{item.is_published ? "Опубликован" : "Черновик"}</span></div></button>) : <div className="catalog-empty compact"><strong>Пакетов пока нет</strong><span>Добавьте первый диапазон глав.</span></div>}</div>
    <details className="catalog-history"><summary>История изменений · {data.revisions.length}</summary>{data.revisions.map((item) => { const cover = Boolean(item.snapshot?.cover_object_key); return <div key={item.id}><div><strong>Версия {item.revision}{cover ? " · с обложкой" : ""}</strong><small>{item.reason} · {date(item.created_at)}</small></div><button onClick={() => onRollback(item)}>{cover ? "Восстановить всё" : "Восстановить"}</button></div>; })}</details>
  </>;
}

export function ReleaseDrawer({ state, grouped, busy, onClose, onEdit, onPreview, onPublication, onUpload, onActivate, onRollback }:{
  state: DataState<ReleaseDetail>;
  grouped: Record<string, FileVersion[]>;
  busy:boolean;
  onClose:()=>void;
  onEdit:(item:Release)=>void;
  onPreview:(item:Release)=>void;
  onPublication:(item:Release)=>void;
  onUpload:(item:Release, kind:string, file:File)=>void;
  onActivate:(item:FileVersion)=>void;
  onRollback:(item:Release, revision:Revision)=>void;
}) {
  return <div className="catalog-release-drawer" role="dialog" aria-modal="true" aria-label="Карточка пакета глав">
    <button className="catalog-drawer-close" aria-label="Закрыть" onClick={onClose}>×</button>
    {state.loading || !state.data ? <Loading label="Загружаем пакет…"/> : <>
      <header><div><Badge value={state.data.release.validation_status}/><h2>{state.data.title?.english_title}</h2><p>{state.data.release.display_name || state.data.release.chapter_label}</p></div><button className={state.data.release.is_published ? "danger-soft" : "primary"} onClick={() => onPublication(state.data!.release)}>{state.data.release.is_published ? "Снять с публикации" : "Опубликовать"}</button></header>
      <div className="catalog-actions"><button onClick={() => onEdit(state.data!.release)}>Изменить данные</button><button onClick={() => onPreview(state.data!.release)}>Предпросмотр</button><label>Загрузить PDF<input hidden type="file" accept=".pdf" disabled={busy} onChange={(event) => event.target.files?.[0] && onUpload(state.data!.release, "pdf", event.target.files[0])}/></label><label>Загрузить EPUB<input hidden type="file" accept=".epub" disabled={busy} onChange={(event) => event.target.files?.[0] && onUpload(state.data!.release, "epub", event.target.files[0])}/></label></div>
      {Object.entries(grouped).map(([kind, items]) => <section className="catalog-file-group" key={kind}><h3>{kind === "pdf" ? "PDF" : "EPUB"}</h3>{items.map((item) => <div key={item.id} className={item.is_active ? "active" : ""}><div><strong>Версия {item.version} · {item.filename}</strong><small>{bytes(item.size_bytes)} · загружено {date(item.created_at)}</small></div>{item.is_active ? <Badge value="valid"/> : <button onClick={() => onActivate(item)}>Использовать эту версию</button>}</div>)}</section>)}
      {!Object.keys(grouped).length && <div className="catalog-empty compact"><strong>Файлы ещё не загружены</strong><span>Для публикации нужны PDF и EPUB.</span></div>}
      <details className="catalog-history"><summary>История пакета · {state.data.revisions.length}</summary>{state.data.revisions.map((item) => <div key={item.id}><div><strong>Версия {item.revision}</strong><small>{item.reason} · {date(item.created_at)}</small></div><button onClick={() => onRollback(state.data!.release, item)}>Восстановить</button></div>)}</details>
    </>}
  </div>;
}
