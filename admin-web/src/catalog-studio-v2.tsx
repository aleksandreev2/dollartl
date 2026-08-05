import React, { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { Badge, ErrorBox, Header, Icon, Loading, date, useData, useToast } from "./admin-ui";
import { catalogMetadataActions } from "./catalog-studio-metadata-actions";
import { catalogFileActions } from "./catalog-studio-file-actions";
import { CleanupDialog, CreateReleaseDialog, CreateTitleDialog, EditReleaseDialog, EditTitleDialog, PreviewDialog, ReasonDialog } from "./catalog-studio-dialogs";
import { ReleaseDrawer, TitleWorkspace } from "./catalog-studio-workspaces";
import "./catalog-studio-v2.css";
import type { CatalogModal, FailedPublication, FileVersion, ReleaseDetail, TitleDetail, TitlePage } from "./catalog-studio-types";

function hashValue(key: string) {
  return new URLSearchParams(window.location.hash.slice(1)).get(key) || "";
}

function setCatalogHash(values: Record<string, string | number | null>) {
  const params = new URLSearchParams(window.location.hash.slice(1));
  for (const [key, value] of Object.entries(values)) {
    if (value === null || value === "" || value === 0) params.delete(key);
    else params.set(key, String(value));
  }
  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#${params.toString()}`);
}

export function CatalogStudioView() {
  const [query, setQuery] = useState(() => hashValue("catalog_q"));
  const [status, setStatus] = useState(() => hashValue("catalog_status") || "all");
  const [page, setPage] = useState(() => Math.max(1, Number(hashValue("catalog_page")) || 1));
  const [selectedTitle, setSelectedTitle] = useState<string | null>(() => hashValue("title") || null);
  const [selectedRelease, setSelectedRelease] = useState<string | null>(() => hashValue("release") || null);
  const [failedSelected, setFailedSelected] = useState<string[]>([]);
  const [modal, setModal] = useState<CatalogModal>(null);
  const [busy, setBusy] = useState(false);
  const { push } = useToast();

  const list = useData(() => api<TitlePage>(`/catalog/titles?q=${encodeURIComponent(query)}&status=${status}&page=${page}`), [query, status, page]);
  const detail = useData(() => selectedTitle ? api<TitleDetail>(`/catalog/titles/${selectedTitle}`) : Promise.resolve(null as unknown as TitleDetail), [selectedTitle]);
  const release = useData(() => selectedRelease ? api<ReleaseDetail>(`/catalog/releases/${selectedRelease}`) : Promise.resolve(null as unknown as ReleaseDetail), [selectedRelease]);
  const failed = useData(() => api<FailedPublication[]>("/catalog/channel/failed-publications"), []);
  const grouped = useMemo(() => {
    const result: Record<string, FileVersion[]> = {};
    for (const item of release.data?.files || []) (result[item.file_kind] ||= []).push(item);
    return result;
  }, [release.data]);

  useEffect(() => setCatalogHash({
    catalog_q: query,
    catalog_status: status === "all" ? null : status,
    catalog_page: page === 1 ? null : page,
    title: selectedTitle,
    release: selectedRelease,
  }), [query, status, page, selectedTitle, selectedRelease]);

  async function refresh() {
    await Promise.all([list.reload(), detail.reload(), release.reload(), failed.reload()]);
  }

  const meta = catalogMetadataActions({ list, detail, release, setModal, setBusy, setSelectedTitle, setSelectedRelease, refresh, push });
  const files = catalogFileActions({ release, failed, setModal, setBusy, setFailedSelected, push });

  async function runReason(reason: string) {
    if (modal?.kind !== "reason") return;
    setBusy(true);
    try { await modal.action.run(reason); setModal(null); }
    catch (cause) { push(cause instanceof Error ? cause.message : String(cause), "error"); }
    finally { setBusy(false); }
  }

  return <section className="page catalog-studio">
    <Header title="Catalog Studio" description="Метаданные, публикации, обложки, версии файлов, preview и recovery." action={<div className="catalog-head-actions"><button disabled={busy} onClick={files.cleanupPreview}>Dry-run очистки</button><button className="primary" onClick={() => setModal({ kind: "create-title" })}>Новый тайтл</button></div>}/>
    {list.error && <ErrorBox text={list.error}/>} 
    <div className="catalog-toolbar"><label><Icon name="search"/><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="Название, alias или slug" aria-label="Поиск тайтлов"/></label><select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }} aria-label="Фильтр каталога"><option value="all">Все</option><option value="published">Опубликованные</option><option value="draft">Черновики</option><option value="ongoing">Продолжаются</option><option value="completed">Завершены</option><option value="hiatus">Пауза</option></select></div>
    <div className="catalog-layout">
      <div className="panel catalog-list">
        <div className="catalog-list-head"><strong>Тайтлы</strong><span>{list.data?.total || 0}</span></div>
        {list.loading ? <Loading label="Загружаем каталог…"/> : list.data?.items.length ? list.data.items.map((item) => <button className={`catalog-title-row${selectedTitle === item.id ? " active" : ""}`} key={item.id} onClick={() => { setSelectedTitle(item.id); setSelectedRelease(null); }} aria-current={selectedTitle === item.id ? "true" : undefined}><div><strong>{item.english_title}</strong><small>{item.original_title}</small></div><div><Badge value={item.is_published ? "completed" : "draft"}/><small>{item.release_count} пак.</small></div></button>) : <div className="catalog-empty compact"><strong>Тайтлы не найдены</strong><span>Измените поиск или фильтр.</span></div>}
        <div className="catalog-pager"><button disabled={page <= 1} onClick={() => setPage(page - 1)}>Назад</button><span>{page}/{list.data?.pages || 1}</span><button disabled={page >= (list.data?.pages || 1)} onClick={() => setPage(page + 1)}>Далее</button></div>
      </div>
      <div className="panel catalog-detail">{!selectedTitle ? <div className="catalog-empty"><Icon name="book" size={36}/><strong>Выберите тайтл</strong><span>Откроется рабочая карточка и история.</span></div> : detail.loading || !detail.data ? <Loading label="Загружаем тайтл…"/> : <TitleWorkspace data={detail.data} onEdit={() => setModal({ kind: "edit-title", title: detail.data!.title })} onPreview={() => files.preview("titles", detail.data!.title.id, detail.data!.title.english_title)} onCover={(file) => meta.replaceCover(detail.data!.title, file)} onPublication={() => meta.publication("titles", detail.data!.title, !detail.data!.title.is_published)} onNewRelease={() => setModal({ kind: "create-release", title: detail.data!.title })} onOpenRelease={setSelectedRelease} onRollback={(revision) => meta.rollback("titles", detail.data!.title.id, revision, detail.data!.title.updated_at)}/>}</div>
    </div>
    <section className="catalog-recovery panel"><div className="catalog-section-head"><div><h3>Recovery публикаций</h3><p>Batch retry только после dry-run и с idempotency key.</p></div><button disabled={!failedSelected.length || busy} onClick={() => files.retryFailed(failedSelected)}>Повторить ({failedSelected.length})</button></div>{failed.loading ? <Loading label="Проверяем failed-публикации…"/> : failed.data?.length ? <div className="catalog-failed-list">{failed.data.map((item) => <label key={item.id}><input type="checkbox" checked={failedSelected.includes(item.id)} onChange={(event) => setFailedSelected((current) => event.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id))}/><div><strong>{item.target_type} · {item.target_id}</strong><small>{item.error || "Неизвестная ошибка"}</small></div><span>{date(item.updated_at)}</span></label>)}</div> : <div className="catalog-empty compact"><strong>Неудачных публикаций нет</strong></div>}</section>

    {selectedRelease && <ReleaseDrawer state={release} grouped={grouped} busy={busy} onClose={() => setSelectedRelease(null)} onEdit={(item) => setModal({ kind: "edit-release", release: item })} onPreview={(item) => files.preview("releases", item.id, item.chapter_label)} onPublication={(item) => meta.publication("releases", item, !item.is_published)} onUpload={files.upload} onActivate={files.activate} onRollback={(item, revision) => meta.rollback("releases", item.id, revision, item.updated_at)}/>} 
    {modal?.kind === "create-title" && <CreateTitleDialog onClose={() => setModal(null)} onSubmit={meta.createTitle}/>} 
    {modal?.kind === "create-release" && <CreateReleaseDialog title={modal.title} onClose={() => setModal(null)} onSubmit={(event) => meta.createRelease(event, modal.title)}/>} 
    {modal?.kind === "edit-title" && <EditTitleDialog item={modal.title} onClose={() => setModal(null)} onSubmit={(event) => meta.saveTitle(event, modal.title)}/>} 
    {modal?.kind === "edit-release" && <EditReleaseDialog item={modal.release} onClose={() => setModal(null)} onSubmit={(event) => meta.saveRelease(event, modal.release)}/>} 
    {modal?.kind === "preview" && <PreviewDialog title={modal.title} data={modal.data} onClose={() => setModal(null)}/>} 
    {modal?.kind === "cleanup" && <CleanupDialog data={modal.data} busy={busy} onClose={() => setModal(null)} onExecute={() => files.cleanupExecute(modal.data, modal.key)}/>} 
    {modal?.kind === "reason" && <ReasonDialog action={modal.action} busy={busy} onClose={() => setModal(null)} onSubmit={runReason}/>} 
  </section>;
}
