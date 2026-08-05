import React from "react";
import { Badge, Icon, Loading, bytes, date } from "./admin-ui";
import type { DataState, FileVersion, Release, ReleaseDetail, Revision, TitleDetail } from "./catalog-studio-types";

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
      <div><div className="catalog-title-state"><Badge value={title.is_published ? "completed" : "draft"}/><span>{title.slug}</span></div><h2>{title.english_title}</h2><p>{title.original_title}</p><small>{title.aliases.join(" · ")}</small></div>
    </div>
    <div className="catalog-actions"><button onClick={onEdit}>Редактировать</button><button onClick={onPreview}>Preview</button><label>Обложка<input hidden type="file" accept="image/*" onChange={(event) => event.target.files?.[0] && onCover(event.target.files[0])}/></label><button className={title.is_published ? "danger-soft" : "primary"} onClick={onPublication}>{title.is_published ? "Снять" : "Опубликовать"}</button></div>
    <div className="catalog-description"><h3>Описание</h3><p>{title.description || "Не добавлено"}</p><dl><dt>Статус</dt><dd>{title.publication_status}</dd><dt>Главы</dt><dd>{title.latest_chapter}</dd><dt>Boosty</dt><dd>{title.boosty_url || "—"}</dd></dl></div>
    <div className="catalog-section-head"><div><h3>Пакеты</h3><p>Редактирование, публикация и версии файлов.</p></div><button onClick={onNewRelease}>Новый пакет</button></div>
    <div className="catalog-release-grid">{data.releases.map((item) => <button key={item.id} onClick={() => onOpenRelease(item.id)}><div><strong>{item.chapter_label}</strong><small>{item.validation_message || "Проверка не завершена"}</small></div><div><Badge value={item.validation_status}/><span>{item.is_published ? "online" : "draft"}</span></div></button>)}</div>
    <details className="catalog-history"><summary>История тайтла · {data.revisions.length}</summary>{data.revisions.map((item) => { const cover = Boolean(item.snapshot?.cover_object_key); return <div key={item.id}><div><strong>Revision {item.revision}{cover ? " · cover snapshot" : ""}</strong><small>{item.reason} · {date(item.created_at)}</small></div><button onClick={() => onRollback(item)}>{cover ? "Тайтл + обложка" : "Восстановить"}</button></div>; })}</details>
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
  return <div className="catalog-release-drawer" role="dialog" aria-modal="true" aria-label="Карточка пакета">
    <button className="catalog-drawer-close" aria-label="Закрыть" onClick={onClose}>×</button>
    {state.loading || !state.data ? <Loading label="Загружаем пакет…"/> : <>
      <header><div><Badge value={state.data.release.validation_status}/><h2>{state.data.title?.english_title}</h2><p>{state.data.release.chapter_label}</p></div><button className={state.data.release.is_published ? "danger-soft" : "primary"} onClick={() => onPublication(state.data!.release)}>{state.data.release.is_published ? "Снять" : "Опубликовать"}</button></header>
      <div className="catalog-actions"><button onClick={() => onEdit(state.data!.release)}>Редактировать</button><button onClick={() => onPreview(state.data!.release)}>Preview</button><label>PDF<input hidden type="file" accept=".pdf" disabled={busy} onChange={(event) => event.target.files?.[0] && onUpload(state.data!.release, "pdf", event.target.files[0])}/></label><label>EPUB<input hidden type="file" accept=".epub" disabled={busy} onChange={(event) => event.target.files?.[0] && onUpload(state.data!.release, "epub", event.target.files[0])}/></label></div>
      {Object.entries(grouped).map(([kind, items]) => <section className="catalog-file-group" key={kind}><h3>{kind.toUpperCase()}</h3>{items.map((item) => <div key={item.id} className={item.is_active ? "active" : ""}><div><strong>v{item.version} · {item.filename}</strong><small>{bytes(item.size_bytes)} · {item.sha256.slice(0, 14)}… · {date(item.created_at)}</small></div>{item.is_active ? <Badge value="valid"/> : <button onClick={() => onActivate(item)}>Активировать</button>}</div>)}</section>)}
      <details className="catalog-history"><summary>История пакета · {state.data.revisions.length}</summary>{state.data.revisions.map((item) => <div key={item.id}><div><strong>Revision {item.revision}</strong><small>{item.reason} · {date(item.created_at)}</small></div><button onClick={() => onRollback(state.data!.release, item)}>Восстановить</button></div>)}</details>
    </>}
  </div>;
}
