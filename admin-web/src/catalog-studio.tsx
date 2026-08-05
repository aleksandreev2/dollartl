import React, { FormEvent, useMemo, useState } from "react";
import { api, confirmAction } from "./api";
import { Badge, ErrorBox, Header, Icon, Loading, Notice, bytes, date, useData } from "./admin-ui";

type Title = { id:string; slug:string; english_title:string; original_title:string; original_language:string; description:string; publication_status:string; boosty_url?:string|null; is_published:boolean; latest_chapter:number; updated_at:string; aliases:string[]; release_count:number };
type Release = { id:string; title_id:string; chapter_start:number; chapter_end:number; chapter_label:string; display_name?:string|null; boosty_url?:string|null; is_published:boolean; comments_enabled:boolean; validation_status:string; validation_message?:string|null; updated_at:string };
type Revision = { id:string; revision:number; reason:string; created_at:string };
type FileVersion = { id:string; file_kind:string; version:number; filename:string; size_bytes:number; sha256:string; is_active:boolean; created_at:string };
type Page = { page:number; pages:number; total:number; items:Title[] };
type Detail = { title:Title; cover_url?:string|null; releases:Release[]; revisions:Revision[] };
type ReleaseDetail = { release:Release; title?:{english_title:string}|null; files:FileVersion[]; revisions:Revision[] };
type Preview = { bot_html:string; channel_html:string; warnings:string[] };
type Cleanup = { candidate_count:number; bytes:number; confirmation:string; items:Array<{id:string;filename:string;version:number;size_bytes:number;created_at:string}> };
type Failed = { id:string; target_type:string; target_id:string; error?:string|null; updated_at:string };
type Modal =
  | { kind:"create-title" }
  | { kind:"create-release"; title:Title }
  | { kind:"edit-title"; title:Title }
  | { kind:"edit-release"; release:Release }
  | { kind:"preview"; title:string; data:Preview }
  | { kind:"cleanup"; data:Cleanup; key:string }
  | null;

function ModalShell({ title, onClose, children }:{ title:string; onClose:()=>void; children:React.ReactNode }) {
  return <div className="catalog-modal-backdrop" onMouseDown={(event: React.MouseEvent<HTMLDivElement>) => event.target === event.currentTarget && onClose()}><div className="catalog-modal"><header><div><h2>{title}</h2><p>Изменения фиксируются в audit и истории версий.</p></div><button onClick={onClose}>×</button></header>{children}</div></div>;
}

function reason(message:string) { return window.prompt(message, "Admin update")?.trim() || ""; }
function key(prefix:string) { return `${prefix}:${Date.now()}:${crypto.randomUUID()}`; }

export function CatalogStudioView() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(1);
  const [selectedTitle, setSelectedTitle] = useState<string | null>(null);
  const [selectedRelease, setSelectedRelease] = useState<string | null>(null);
  const [modal, setModal] = useState<Modal>(null);
  const [notice, setNotice] = useState("");
  const [failedSelected, setFailedSelected] = useState<string[]>([]);
  const list = useData(() => api<Page>(`/catalog/titles?q=${encodeURIComponent(query)}&status=${status}&page=${page}`), [query, status, page]);
  const detail = useData(() => selectedTitle ? api<Detail>(`/catalog/titles/${selectedTitle}`) : Promise.resolve(null as unknown as Detail), [selectedTitle]);
  const release = useData(() => selectedRelease ? api<ReleaseDetail>(`/catalog/releases/${selectedRelease}`) : Promise.resolve(null as unknown as ReleaseDetail), [selectedRelease]);
  const failed = useData(() => api<Failed[]>("/catalog/channel/failed-publications"), []);
  const grouped = useMemo(() => {
    const result:Record<string, FileVersion[]> = {};
    for (const item of release.data?.files || []) (result[item.file_kind] ||= []).push(item);
    return result;
  }, [release.data]);

  async function refresh() { await Promise.all([list.reload(), detail.reload(), release.reload(), failed.reload()]); }
  async function createTitle(event:FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    try {
      const item = await api<Title>("/titles", { method:"POST", body:JSON.stringify({ english_title:form.get("english_title"), original_title:form.get("original_title"), original_language:form.get("original_language"), publication_status:form.get("publication_status"), description:form.get("description") || "", boosty_url:form.get("boosty_url") || null, aliases:String(form.get("aliases") || "").split("\n").map(v=>v.trim()).filter(Boolean) }) });
      setModal(null); setSelectedTitle(item.id); await list.reload(); setNotice("Тайтл создан.");
    } catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }
  async function createRelease(event:FormEvent<HTMLFormElement>, title:Title) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    try {
      const item = await api<Release>("/releases", { method:"POST", body:JSON.stringify({ title_id:title.id, chapter_start:Number(form.get("chapter_start")), chapter_end:Number(form.get("chapter_end")), display_name:form.get("display_name") || null, boosty_url:form.get("boosty_url") || null }) });
      setModal(null); setSelectedRelease(item.id); await detail.reload(); setNotice("Пакет создан.");
    } catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }
  async function saveTitle(event:FormEvent<HTMLFormElement>, item:Title) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    try {
      await api(`/catalog/titles/${item.id}`, { method:"PUT", body:JSON.stringify({ slug:form.get("slug"), english_title:form.get("english_title"), original_title:form.get("original_title"), original_language:form.get("original_language"), publication_status:form.get("publication_status"), description:form.get("description") || "", boosty_url:form.get("boosty_url") || null, aliases:String(form.get("aliases") || "").split("\n").map(v=>v.trim()).filter(Boolean), reason:form.get("reason"), expected_updated_at:item.updated_at }) });
      setModal(null); await refresh(); setNotice("Тайтл обновлён.");
    } catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }
  async function saveRelease(event:FormEvent<HTMLFormElement>, item:Release) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    try {
      await api(`/catalog/releases/${item.id}`, { method:"PUT", body:JSON.stringify({ chapter_start:Number(form.get("chapter_start")), chapter_end:Number(form.get("chapter_end")), display_name:form.get("display_name") || null, boosty_url:form.get("boosty_url") || null, comments_enabled:form.get("comments_enabled") === "on", reason:form.get("reason"), expected_updated_at:item.updated_at }) });
      setModal(null); await refresh(); setNotice("Пакет обновлён.");
    } catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }
  async function publication(kind:"titles"|"releases", item:Title|Release, published:boolean) {
    const why = reason(published ? "Причина публикации:" : "Причина снятия с публикации:"); if (!why) return;
    if (!(await confirmAction(published ? "Опубликовать?" : "Снять с публикации?"))) return;
    try { await api(`/catalog/${kind}/${item.id}/publication`, { method:"POST", body:JSON.stringify({ published, reason:why, expected_updated_at:item.updated_at }) }); await refresh(); setNotice(published ? "Опубликовано." : "Снято с публикации."); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }
  async function rollback(kind:"titles"|"releases", id:string, revision:Revision, updatedAt:string) {
    const why = reason(`Причина rollback к revision ${revision.revision}:`); if (!why) return;
    if (!(await confirmAction(`Восстановить revision ${revision.revision}?`))) return;
    try { await api(`/catalog/${kind}/${id}/rollback/${revision.id}`, { method:"POST", body:JSON.stringify({ reason:why, expected_updated_at:updatedAt }) }); await refresh(); setNotice("Версия восстановлена."); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }
  async function cover(item:Title, file:File) {
    const why = reason("Причина замены обложки:"); if (!why) return;
    const body = new FormData(); body.set("file", file);
    try { await api(`/catalog/titles/${item.id}/cover?expected_updated_at=${encodeURIComponent(item.updated_at)}&reason=${encodeURIComponent(why)}`, { method:"POST", body }); await refresh(); setNotice("Обложка обновлена."); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }
  async function upload(item:Release, kind:string, file:File) {
    const body = new FormData(); body.set("file", file);
    try { await api(`/catalog/releases/${item.id}/files/${kind}`, { method:"POST", body }); await refresh(); setNotice(`${kind.toUpperCase()} загружен новой версией.`); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }
  async function activate(item:FileVersion) {
    const why = reason(`Причина активации ${item.file_kind.toUpperCase()} v${item.version}:`); if (!why) return;
    try { await api(`/catalog/file-versions/${item.id}/activate`, { method:"POST", body:JSON.stringify({ reason:why }) }); await release.reload(); setNotice("Версия файла активирована."); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }
  async function preview(kind:"titles"|"releases", id:string, title:string) {
    try { setModal({ kind:"preview", title, data:await api<Preview>(`/catalog/${kind}/${id}/preview`) }); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }
  async function cleanupPreview() {
    const idempotency = key("cleanup");
    try { const data = await api<Cleanup>("/catalog/files/cleanup", { method:"POST", body:JSON.stringify({ dry_run:true, min_age_days:30, idempotency_key:idempotency }) }); setModal({ kind:"cleanup", data, key:idempotency }); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }
  async function cleanupExecute(data:Cleanup, idempotency:string) {
    if (!(await confirmAction(`Удалить ${data.candidate_count} неиспользуемых версий?`))) return;
    try { const result = await api<{deleted_count:number;failed_count:number}>("/catalog/files/cleanup", { method:"POST", body:JSON.stringify({ dry_run:false, min_age_days:30, idempotency_key:idempotency, confirmation:data.confirmation }) }); setModal(null); setNotice(`Удалено ${result.deleted_count}, ошибок ${result.failed_count}.`); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }
  async function retryFailed() {
    if (!failedSelected.length) return;
    const idempotency = key("retry-publications");
    try {
      const preview = await api<{eligible:number}>("/catalog/channel/retry-failed", { method:"POST", body:JSON.stringify({ publication_ids:failedSelected, dry_run:true, idempotency_key:idempotency }) });
      if (!(await confirmAction(`Вернуть в очередь ${preview.eligible} публикаций?`))) return;
      const result = await api<{retried:number}>("/catalog/channel/retry-failed", { method:"POST", body:JSON.stringify({ publication_ids:failedSelected, dry_run:false, idempotency_key:idempotency }) });
      setFailedSelected([]); await failed.reload(); setNotice(`В очередь возвращено: ${result.retried}.`);
    } catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }

  return <section className="page catalog-studio">
    <Header title="Catalog Studio" description="Метаданные, публикации, обложки, версии файлов, preview и recovery." action={<div className="catalog-head-actions"><button onClick={cleanupPreview}>Dry-run очистки</button><button className="primary" onClick={() => setModal({kind:"create-title"})}>Новый тайтл</button></div>}/>
    {notice && <Notice text={notice}/>} {list.error && <ErrorBox text={list.error}/>} 
    <div className="catalog-toolbar"><label><Icon name="search"/><input value={query} onChange={(event: React.ChangeEvent<HTMLInputElement>) => { setQuery(event.target.value); setPage(1); }} placeholder="Название, alias или slug"/></label><select value={status} onChange={(event: React.ChangeEvent<HTMLSelectElement>) => { setStatus(event.target.value); setPage(1); }}><option value="all">Все</option><option value="published">Опубликованные</option><option value="draft">Черновики</option><option value="ongoing">Продолжаются</option><option value="completed">Завершены</option><option value="hiatus">Пауза</option></select></div>
    <div className="catalog-layout">
      <div className="panel catalog-list"><div className="catalog-list-head"><strong>Тайтлы</strong><span>{list.data?.total || 0}</span></div>{list.loading ? <Loading/> : list.data?.items.map((item) => <button className={`catalog-title-row${selectedTitle === item.id ? " active" : ""}`} key={item.id} onClick={() => { setSelectedTitle(item.id); setSelectedRelease(null); }}><div><strong>{item.english_title}</strong><small>{item.original_title}</small></div><div><Badge value={item.is_published ? "completed" : "draft"}/><small>{item.release_count} пак.</small></div></button>)}<div className="catalog-pager"><button disabled={page <= 1} onClick={() => setPage(page - 1)}>Назад</button><span>{page}/{list.data?.pages || 1}</span><button disabled={page >= (list.data?.pages || 1)} onClick={() => setPage(page + 1)}>Далее</button></div></div>
      <div className="panel catalog-detail">{!selectedTitle ? <div className="catalog-empty"><Icon name="book" size={36}/><strong>Выберите тайтл</strong><span>Откроется рабочая карточка и история.</span></div> : detail.loading || !detail.data ? <Loading/> : <><div className="catalog-title-hero">{detail.data.cover_url ? <img src={detail.data.cover_url} alt=""/> : <div className="catalog-cover-empty"><Icon name="book" size={30}/></div>}<div><div className="catalog-title-state"><Badge value={detail.data.title.is_published ? "completed" : "draft"}/><span>{detail.data.title.slug}</span></div><h2>{detail.data.title.english_title}</h2><p>{detail.data.title.original_title}</p><small>{detail.data.title.aliases.join(" · ")}</small></div></div><div className="catalog-actions"><button onClick={() => setModal({kind:"edit-title", title:detail.data!.title})}>Редактировать</button><button onClick={() => preview("titles", detail.data!.title.id, detail.data!.title.english_title)}>Preview</button><label>Обложка<input hidden type="file" accept="image/*" onChange={(event: React.ChangeEvent<HTMLInputElement>) => event.target.files?.[0] && cover(detail.data!.title, event.target.files[0])}/></label><button className={detail.data.title.is_published ? "danger-soft" : "primary"} onClick={() => publication("titles", detail.data!.title, !detail.data!.title.is_published)}>{detail.data.title.is_published ? "Снять" : "Опубликовать"}</button></div><div className="catalog-description"><h3>Описание</h3><p>{detail.data.title.description || "Не добавлено"}</p><dl><dt>Статус</dt><dd>{detail.data.title.publication_status}</dd><dt>Главы</dt><dd>{detail.data.title.latest_chapter}</dd><dt>Boosty</dt><dd>{detail.data.title.boosty_url || "—"}</dd></dl></div><div className="catalog-section-head"><div><h3>Пакеты</h3><p>Редактирование, публикация и версии файлов.</p></div><button onClick={() => setModal({kind:"create-release", title:detail.data!.title})}>Новый пакет</button></div><div className="catalog-release-grid">{detail.data.releases.map((item) => <button key={item.id} onClick={() => setSelectedRelease(item.id)}><div><strong>{item.chapter_label}</strong><small>{item.validation_message || "Проверка не завершена"}</small></div><div><Badge value={item.validation_status}/><span>{item.is_published ? "online" : "draft"}</span></div></button>)}</div><details className="catalog-history"><summary>История тайтла · {detail.data.revisions.length}</summary>{detail.data.revisions.map((item) => <div key={item.id}><div><strong>Revision {item.revision}</strong><small>{item.reason} · {date(item.created_at)}</small></div><button onClick={() => rollback("titles", detail.data!.title.id, item, detail.data!.title.updated_at)}>Восстановить</button></div>)}</details></>}</div>
    </div>
    <section className="catalog-recovery panel"><div className="catalog-section-head"><div><h3>Recovery публикаций</h3><p>Batch retry только после dry-run и с idempotency key.</p></div><button disabled={!failedSelected.length} onClick={retryFailed}>Повторить ({failedSelected.length})</button></div>{failed.data?.length ? <div className="catalog-failed-list">{failed.data.map((item) => <label key={item.id}><input type="checkbox" checked={failedSelected.includes(item.id)} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setFailedSelected(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))}/><div><strong>{item.target_type} · {item.target_id}</strong><small>{item.error || "Неизвестная ошибка"}</small></div><span>{date(item.updated_at)}</span></label>)}</div> : <div className="catalog-empty compact"><strong>Неудачных публикаций нет</strong></div>}</section>

    {selectedRelease && <div className="catalog-release-drawer"><button className="catalog-drawer-close" onClick={() => setSelectedRelease(null)}>×</button>{release.loading || !release.data ? <Loading/> : <><header><div><Badge value={release.data.release.validation_status}/><h2>{release.data.title?.english_title}</h2><p>{release.data.release.chapter_label}</p></div><button className={release.data.release.is_published ? "danger-soft" : "primary"} onClick={() => publication("releases", release.data!.release, !release.data!.release.is_published)}>{release.data.release.is_published ? "Снять" : "Опубликовать"}</button></header><div className="catalog-actions"><button onClick={() => setModal({kind:"edit-release", release:release.data!.release})}>Редактировать</button><button onClick={() => preview("releases", release.data!.release.id, release.data!.release.chapter_label)}>Preview</button><label>PDF<input hidden type="file" accept=".pdf" onChange={(event: React.ChangeEvent<HTMLInputElement>) => event.target.files?.[0] && upload(release.data!.release, "pdf", event.target.files[0])}/></label><label>EPUB<input hidden type="file" accept=".epub" onChange={(event: React.ChangeEvent<HTMLInputElement>) => event.target.files?.[0] && upload(release.data!.release, "epub", event.target.files[0])}/></label></div>{Object.entries(grouped).map(([kind, items]) => <section className="catalog-file-group" key={kind}><h3>{kind.toUpperCase()}</h3>{items.map((item) => <div key={item.id} className={item.is_active ? "active" : ""}><div><strong>v{item.version} · {item.filename}</strong><small>{bytes(item.size_bytes)} · {item.sha256.slice(0,14)}… · {date(item.created_at)}</small></div>{item.is_active ? <Badge value="valid"/> : <button onClick={() => activate(item)}>Активировать</button>}</div>)}</section>)}<details className="catalog-history"><summary>История пакета · {release.data.revisions.length}</summary>{release.data.revisions.map((item) => <div key={item.id}><div><strong>Revision {item.revision}</strong><small>{item.reason} · {date(item.created_at)}</small></div><button onClick={() => rollback("releases", release.data!.release.id, item, release.data!.release.updated_at)}>Восстановить</button></div>)}</details></>}</div>}

    {modal?.kind === "create-title" && <ModalShell title="Новый тайтл" onClose={() => setModal(null)}><form className="catalog-form" onSubmit={createTitle}><div className="row"><label>Английское название<input name="english_title" required/></label><label>Оригинальное название<input name="original_title" required/></label></div><div className="row"><label>Язык<input name="original_language" required/></label><label>Статус<select name="publication_status" defaultValue="ongoing"><option value="ongoing">Продолжается</option><option value="completed">Завершён</option><option value="hiatus">Пауза</option></select></label></div><label>Aliases<textarea name="aliases" rows={4}/></label><label>Boosty URL<input name="boosty_url" type="url"/></label><label>Описание<textarea name="description" rows={7}/></label><footer><button type="button" onClick={() => setModal(null)}>Отмена</button><button className="primary">Создать</button></footer></form></ModalShell>}
    {modal?.kind === "create-release" && <ModalShell title={`Новый пакет · ${modal.title.english_title}`} onClose={() => setModal(null)}><form className="catalog-form" onSubmit={(event: React.FormEvent<HTMLFormElement>) => createRelease(event, modal.title)}><div className="row"><label>С главы<input name="chapter_start" type="number" min="0" required/></label><label>По главу<input name="chapter_end" type="number" min="0" required/></label></div><label>Название<input name="display_name"/></label><label>Boosty URL<input name="boosty_url" type="url"/></label><footer><button type="button" onClick={() => setModal(null)}>Отмена</button><button className="primary">Создать</button></footer></form></ModalShell>}
    {modal?.kind === "edit-title" && <ModalShell title="Редактирование тайтла" onClose={() => setModal(null)}><form className="catalog-form" onSubmit={(event: React.FormEvent<HTMLFormElement>) => saveTitle(event, modal.title)}><label>Slug<input name="slug" defaultValue={modal.title.slug} required pattern="[a-z0-9]+(?:-[a-z0-9]+)*"/></label><div className="row"><label>Английское<input name="english_title" defaultValue={modal.title.english_title} required/></label><label>Оригинальное<input name="original_title" defaultValue={modal.title.original_title} required/></label></div><div className="row"><label>Язык<input name="original_language" defaultValue={modal.title.original_language} required/></label><label>Статус<select name="publication_status" defaultValue={modal.title.publication_status}><option value="ongoing">Продолжается</option><option value="completed">Завершён</option><option value="hiatus">Пауза</option></select></label></div><label>Aliases<textarea name="aliases" rows={5} defaultValue={modal.title.aliases.join("\n")}/></label><label>Boosty URL<input name="boosty_url" type="url" defaultValue={modal.title.boosty_url || ""}/></label><label>Описание<textarea name="description" rows={7} defaultValue={modal.title.description}/></label><label>Причина<input name="reason" required minLength={3}/></label><footer><button type="button" onClick={() => setModal(null)}>Отмена</button><button className="primary">Сохранить</button></footer></form></ModalShell>}
    {modal?.kind === "edit-release" && <ModalShell title="Редактирование пакета" onClose={() => setModal(null)}><form className="catalog-form" onSubmit={(event: React.FormEvent<HTMLFormElement>) => saveRelease(event, modal.release)}><div className="row"><label>С главы<input name="chapter_start" type="number" min="0" defaultValue={modal.release.chapter_start} required/></label><label>По главу<input name="chapter_end" type="number" min="0" defaultValue={modal.release.chapter_end} required/></label></div><label>Название<input name="display_name" defaultValue={modal.release.display_name || ""}/></label><label>Boosty URL<input name="boosty_url" type="url" defaultValue={modal.release.boosty_url || ""}/></label><label className="catalog-checkbox"><input name="comments_enabled" type="checkbox" defaultChecked={modal.release.comments_enabled}/>Комментарии включены</label><label>Причина<input name="reason" required minLength={3}/></label><footer><button type="button" onClick={() => setModal(null)}>Отмена</button><button className="primary">Сохранить</button></footer></form></ModalShell>}
    {modal?.kind === "preview" && <ModalShell title={`Preview · ${modal.title}`} onClose={() => setModal(null)}>{modal.data.warnings.length > 0 && <Notice text={modal.data.warnings.join(" · ")}/>}<div className="catalog-preview-grid"><article><h3>Telegram bot</h3><pre>{modal.data.bot_html}</pre></article><article><h3>Telegram channel</h3><pre>{modal.data.channel_html}</pre></article></div></ModalShell>}
    {modal?.kind === "cleanup" && <ModalShell title="Очистка неактивных файлов" onClose={() => setModal(null)}><div className="catalog-cleanup-summary"><strong>{modal.data.candidate_count} версий</strong><span>{bytes(modal.data.bytes)}</span><code>{modal.data.confirmation}</code></div><div className="catalog-cleanup-list">{modal.data.items.map((item) => <div key={item.id}><span>{item.filename} · v{item.version}</span><small>{bytes(item.size_bytes)} · {date(item.created_at)}</small></div>)}</div><footer className="catalog-modal-footer"><button onClick={() => setModal(null)}>Отмена</button><button className="danger-soft" disabled={!modal.data.candidate_count} onClick={() => cleanupExecute(modal.data, modal.key)}>Удалить после повторной проверки</button></footer></ModalShell>}
  </section>;
}
