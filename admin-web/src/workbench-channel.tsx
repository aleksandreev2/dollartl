import React, { ChangeEvent, useState } from "react";
import { api, confirmAction } from "./api";
import { Badge, ErrorBox, Header, Icon, Loading, Notice, date, useData } from "./admin-ui";
import { Empty, Pager, StatCards, type ChannelItem, type ChannelResponse } from "./workbench-shared";

export function ChannelWorkbenchView() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(1);
  const [notice, setNotice] = useState("");
  const state = useData(() => api<ChannelResponse>(`/channel/publications?q=${encodeURIComponent(query)}&status=${status}&page=${page}&page_size=30`), [query, status, page]);
  async function retry(item: ChannelItem) {
    if (!(await confirmAction(`Повторно поставить публикацию ${item.target_type}:${item.target_id} в очередь?`))) return;
    try { const result = await api<{ outbox_requeued: boolean }>(`/channel/publications/${item.id}/retry`, { method: "POST" }); setNotice(result.outbox_requeued ? "Публикация возвращена в outbox." : "Статус сброшен, но исходное outbox-событие не найдено."); await state.reload(); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }
  const summary = state.data?.summary || {};
  return <section className="page wb-page"><Header title="Telegram-канал" description="Очередь, история и безопасный повтор неудачных публикаций." action={<button className="with-icon" onClick={state.reload}><Icon name="refresh"/>Обновить</button>}/>{notice && <Notice text={notice}/>}<div className={`wb-channel-banner ${state.data?.channel_posts_enabled ? "enabled" : "disabled"}`}><Icon name="telegram" size={24}/><div><strong>{state.data?.channel_username || "Канал не настроен"}</strong><span>{state.data?.channel_posts_enabled ? "Автопубликации включены" : "Автопубликации выключены через environment"}</span></div></div><StatCards entries={[["Отправлено", summary.sent || 0, "good"],["Ожидает", summary.pending || 0, "warn"],["Ошибки", summary.failed || 0, "danger"],["Всего", state.data?.total || 0, "muted"]]}/><div className="wb-toolbar"><label><Icon name="search"/><input value={query} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => { setQuery(event.target.value); setPage(1); }} placeholder="Target ID, канал или ошибка"/></label><select value={status} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => { setStatus(event.target.value); setPage(1); }}><option value="all">Все статусы</option><option value="sent">Отправлено</option><option value="pending">Ожидает</option><option value="failed">Ошибка</option></select></div>{state.error && <ErrorBox text={state.error}/>} {state.loading || !state.data ? <Loading/> : state.data.items.length ? <><div className="wb-table-wrap"><table className="wb-table"><thead><tr><th>Цель</th><th>Канал</th><th>Статус</th><th>Обновлено</th><th></th></tr></thead><tbody>{state.data.items.map(item => <tr key={item.id}><td><strong>{item.target_type}</strong><small className="mono">{item.target_id}</small></td><td><strong>{item.telegram_chat_id}</strong><small>message ID: {item.telegram_message_id || "—"}</small></td><td><Badge value={item.status}/>{item.error && <small className="wb-danger">{item.error}</small>}</td><td>{date(item.updated_at)}</td><td>{item.status === "failed" && <button className="primary-soft" onClick={() => retry(item)}>Повторить</button>}</td></tr>)}</tbody></table></div><Pager page={state.data.page} pages={state.data.pages} total={state.data.total} onPage={setPage}/></> : <Empty text="Публикации не найдены"/>}</section>;
}
