import React, { ChangeEvent, useMemo, useState } from "react";
import { api } from "./api";
import { ErrorBox, Header, Icon, Loading, Notice, date, useData } from "./admin-ui";
import { Empty, Pager, type AuditResponse } from "./workbench-shared";

function downloadText(filename: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = filename; anchor.click();
  URL.revokeObjectURL(url);
}

export function AuditWorkbenchView() {
  const [query, setQuery] = useState("");
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [actor, setActor] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState("");
  const [notice, setNotice] = useState("");
  const params = useMemo(() => { const value = new URLSearchParams({ q: query, action, entity_type: entityType, page: String(page), page_size: "40" }); if (actor.trim()) value.set("actor_telegram_id", actor.trim()); return value.toString(); }, [query, action, entityType, actor, page]);
  const state = useData(() => api<AuditResponse>(`/audit/events?${params}`), [params]);
  async function exportCsv() {
    try { const filters = new URLSearchParams({ q: query, action, entity_type: entityType }); if (actor.trim()) filters.set("actor_telegram_id", actor.trim()); const result = await api<{ filename: string; content: string }>(`/audit/export?${filters.toString()}`); downloadText(result.filename, result.content); setNotice(`Экспортировано событий: до 5000.`); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }
  return <section className="page wb-page"><Header title="Журнал действий" description="Фильтруемый audit timeline с correlation ID и экспортом CSV." action={<div className="wb-header-actions"><button onClick={exportCsv}>Экспорт CSV</button><button className="with-icon" onClick={state.reload}><Icon name="refresh"/>Обновить</button></div>}/>{notice && <Notice text={notice}/>}<div className="wb-toolbar wb-toolbar-audit"><label><Icon name="search"/><input value={query} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => { setQuery(event.target.value); setPage(1); }} placeholder="Действие, сущность, ID или correlation"/></label><select value={action} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => { setAction(event.target.value); setPage(1); }}><option value="">Все действия</option>{state.data?.actions.map(item => <option key={item} value={item}>{item}</option>)}</select><select value={entityType} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => { setEntityType(event.target.value); setPage(1); }}><option value="">Все сущности</option>{state.data?.entity_types.map(item => <option key={item} value={item}>{item}</option>)}</select><input className="wb-actor" inputMode="numeric" value={actor} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => { setActor(event.target.value.replace(/\D/g, "")); setPage(1); }} placeholder="Actor Telegram ID"/></div>{state.error && <ErrorBox text={state.error}/>} {state.loading || !state.data ? <Loading/> : state.data.items.length ? <><div className="wb-audit-list">{state.data.items.map(item => <article key={item.id} className={expanded === item.id ? "expanded" : ""}><button className="wb-audit-main" onClick={() => setExpanded(expanded === item.id ? "" : item.id)}><span className="wb-audit-icon"><Icon name="history"/></span><div><strong>{item.action}</strong><small>{item.entity_type || "system"}{item.entity_id ? ` · ${item.entity_id}` : ""}</small></div><div><span>{date(item.created_at)}</span><small>actor: {item.actor_telegram_id || "system"}</small></div><Icon name="chevron"/></button>{expanded === item.id && <div className="wb-audit-detail"><dl><dt>Correlation ID</dt><dd>{item.correlation_id || "—"}</dd><dt>Audit ID</dt><dd>{item.id}</dd></dl><pre>{JSON.stringify(item.payload, null, 2)}</pre></div>}</article>)}</div><Pager page={state.data.page} pages={state.data.pages} total={state.data.total} onPage={setPage}/></> : <Empty text="События audit не найдены"/>}</section>;
}
