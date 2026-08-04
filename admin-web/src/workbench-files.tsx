import React, { ChangeEvent, useState } from "react";
import { api, confirmAction } from "./api";
import { Badge, ErrorBox, Header, Icon, Loading, Notice, bytes, date, useData } from "./admin-ui";
import { Empty, Pager, StatCards, type FileItem, type FilesResponse } from "./workbench-shared";

export function FilesWorkbenchView() {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [cache, setCache] = useState("all");
  const [active, setActive] = useState("active");
  const [page, setPage] = useState(1);
  const [notice, setNotice] = useState("");
  const [checking, setChecking] = useState("");
  const state = useData(() => api<FilesResponse>(`/files/versions?q=${encodeURIComponent(query)}&kind=${kind}&cache=${cache}&active=${active}&page=${page}&page_size=30`), [query, kind, cache, active, page]);
  async function verify(item: FileItem) {
    setChecking(item.id); setNotice("");
    try { const result = await api<{ ok: boolean; object_exists: boolean; expected_size: number; actual_size?: number | null }>(`/files/versions/${item.id}/verify`, { method: "POST" }); setNotice(result.ok ? `${item.filename}: объект существует, размер совпадает.` : `${item.filename}: проверка не пройдена. S3=${result.object_exists ? result.actual_size : "missing"}, БД=${result.expected_size}.`); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
    finally { setChecking(""); }
  }
  async function clearCache(item: FileItem) {
    if (!(await confirmAction(`Очистить Telegram file_id для ${item.filename}? Следующая выдача загрузит файл заново.`))) return;
    await api(`/files/versions/${item.id}/clear-cache`, { method: "POST" }); setNotice("Telegram-кэш очищен."); await state.reload();
  }
  const summary = state.data?.summary;
  const resetPage = () => setPage(1);
  return <section className="page wb-page"><Header title="Файлы и кэш" description="Версии PDF/EPUB, S3-проверка и управление Telegram file_id." action={<button className="with-icon" onClick={state.reload}><Icon name="refresh"/>Обновить</button>}/>{notice && <Notice text={notice}/>}<StatCards entries={[["Активных версий", summary?.active || 0, "good"],["В Telegram-кэше", summary?.cached || 0, "warn"],["Общий размер", bytes(summary?.bytes || 0), "muted"]]}/><div className="wb-toolbar wb-toolbar-wide"><label><Icon name="search"/><input value={query} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => { setQuery(event.target.value); resetPage(); }} placeholder="Название, файл или SHA-256"/></label><select value={kind} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => { setKind(event.target.value); resetPage(); }}><option value="all">PDF + EPUB</option><option value="pdf">PDF</option><option value="epub">EPUB</option></select><select value={cache} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => { setCache(event.target.value); resetPage(); }}><option value="all">Любой кэш</option><option value="cached">Есть file_id</option><option value="uncached">Без file_id</option></select><select value={active} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => { setActive(event.target.value); resetPage(); }}><option value="active">Активные</option><option value="inactive">Неактивные</option><option value="all">Все версии</option></select></div>{state.error && <ErrorBox text={state.error}/>} {state.loading || !state.data ? <Loading/> : state.data.items.length ? <><div className="wb-table-wrap"><table className="wb-table"><thead><tr><th>Файл</th><th>Релиз</th><th>Версия</th><th>Кэш</th><th>SHA-256</th><th></th></tr></thead><tbody>{state.data.items.map(item => <tr key={item.id}><td><strong>{item.filename}</strong><small>{item.file_kind.toUpperCase()} · {bytes(item.size_bytes)} · {item.content_type}</small></td><td><strong>{item.title}</strong><small>{item.release_label}</small></td><td><span>v{item.version}</span><small>{date(item.created_at)}</small></td><td><Badge value={item.telegram_cached ? "completed" : "pending"}/><small>{item.telegram_cached ? "file_id сохранён" : "загрузка при выдаче"}</small></td><td><code className="wb-sha">{item.sha256}</code></td><td><div className="wb-row-actions"><button disabled={checking === item.id} onClick={() => verify(item)}>{checking === item.id ? "Проверяем…" : "Проверить S3"}</button>{item.telegram_cached && <button className="danger-soft" onClick={() => clearCache(item)}>Очистить кэш</button>}</div></td></tr>)}</tbody></table></div><Pager page={state.data.page} pages={state.data.pages} total={state.data.total} onPage={setPage}/></> : <Empty text="Файлы не найдены"/>}</section>;
}
