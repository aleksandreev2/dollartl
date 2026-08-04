import React, { ChangeEvent, FormEvent, MouseEvent, useState } from "react";
import { api, confirmAction } from "./api";
import { ErrorBox, Header, Icon, Loading, Notice, date, useData } from "./admin-ui";
import { Empty, type SettingsResponse } from "./workbench-shared";

type SettingEditorState = { key: string; value: string; description: string; expected?: string | null; isNew: boolean };

export function SettingsWorkbenchView() {
  const state = useData(() => api<SettingsResponse>("/settings/workbench"), []);
  const [editor, setEditor] = useState<SettingEditorState | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  function edit(item?: SettingsResponse["overrides"][number]) {
    setError("");
    setEditor(item ? { key: item.key, value: JSON.stringify(item.value, null, 2), description: item.description || "", expected: item.updated_at, isNew: false } : { key: "", value: "{\n  \"value\": true\n}", description: "", isNew: true });
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (!editor) return;
    setBusy(true); setError("");
    try { const parsed = JSON.parse(editor.value); await api(`/settings/workbench/${encodeURIComponent(editor.key)}`, { method: "PUT", body: JSON.stringify({ value: parsed, description: editor.description || null, expected_updated_at: editor.expected || null }) }); setEditor(null); setNotice("Override сохранён. Для env-backed значения потребуется синхронизация Railway и redeploy."); await state.reload(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  }
  async function reset(item: SettingsResponse["overrides"][number]) {
    if (!(await confirmAction(`Удалить override ${item.key}? Активным останется значение environment.`))) return;
    try { await api(`/settings/workbench/${encodeURIComponent(item.key)}/reset`, { method: "POST", body: JSON.stringify({ expected_updated_at: item.updated_at || null }) }); setNotice("Override удалён."); await state.reload(); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : String(cause)); }
  }
  return <section className="page wb-page"><Header title="Настройки системы" description="Разделение Railway environment и аудируемых DB overrides без доступа к секретам." action={<button className="primary with-icon" onClick={() => edit()}><span>＋</span>Новый override</button>}/>{notice && <Notice text={notice}/>} {state.error && <ErrorBox text={state.error}/>} {state.loading || !state.data ? <Loading/> : <><div className="wb-setting-notice"><Icon name="shield"/><p>{state.data.notice}</p></div><div className="wb-settings-grid"><article className="panel"><div className="section-heading"><div><h2>DB overrides</h2><p>Версионируемые записи с optimistic conflict detection.</p></div></div>{state.data.overrides.length ? state.data.overrides.map(item => <div className="wb-setting-row" key={item.key}><div><strong>{item.key}</strong><code>{JSON.stringify(item.value)}</code><small>{item.description || "Без описания"} · {date(item.updated_at)}</small></div><div><button onClick={() => edit(item)}>Изменить</button><button className="danger-soft" onClick={() => reset(item)}>Сбросить</button></div></div>) : <Empty text="DB overrides отсутствуют"/>}</article><article className="panel"><div className="section-heading"><div><h2>Railway environment</h2><p>Текущие не секретные значения процесса.</p></div></div>{state.data.environment.map(item => <div className="wb-env-row" key={item.key}><span>{item.key}</span><code>{String(item.value ?? "—")}</code></div>)}</article></div></>}{editor && <div className="wb-modal-backdrop" role="presentation" onMouseDown={(event: MouseEvent<HTMLDivElement>) => event.target === event.currentTarget && setEditor(null)}><form className="wb-modal wb-setting-modal" onSubmit={save}><header><div><h3>{editor.isNew ? "Новый override" : "Изменить override"}</h3><p>Секретные ключи запрещены сервером.</p></div><button type="button" onClick={() => setEditor(null)}>×</button></header>{error && <ErrorBox text={error}/>}<label><span>Ключ</span><input autoFocus={editor.isNew} value={editor.key} disabled={!editor.isNew} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setEditor({ ...editor, key: event.target.value })} pattern="[a-z][a-z0-9_.-]{1,148}" required/></label><label><span>JSON value</span><textarea className="mono" value={editor.value} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setEditor({ ...editor, value: event.target.value })} rows={9} required/></label><label><span>Описание</span><textarea value={editor.description} onChange={(event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setEditor({ ...editor, description: event.target.value })} rows={3}/></label><footer><button type="button" onClick={() => setEditor(null)}>Отмена</button><button className="primary" disabled={busy}>{busy ? "Сохраняем…" : "Сохранить"}</button></footer></form></div>}</section>;
}
