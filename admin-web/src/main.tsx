import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import { api, initializeTelegram } from "./api";
import type { SessionInfo } from "./types";
import { Icon, Loading, sections, ToastProvider, useData, type Section } from "./admin-ui";
import { BroadcastsView } from "./admin-views";
import { CatalogStudioView } from "./catalog-studio";
import { UsersWorkbenchView } from "./admin-people";
import { CommunityWorkbenchView } from "./admin-moderation";
import { SuggestionsWorkbenchView } from "./admin-suggestions";
import { CommandPalette, OperationsOverview } from "./admin-operations";
import {
  AuditWorkbenchView,
  BoostyWorkbenchView,
  ChannelWorkbenchView,
  FilesWorkbenchView,
  SettingsWorkbenchView,
} from "./admin-workbench";
import "./styles.css";
import "./admin-ux.css";
import "./admin-operations.css";
import "./admin-workbench.css";
import "./admin-people.css";
import "./admin-moderation.css";
import "./catalog-studio.css";
import "./admin-final.css";

function sectionFromHash(): Section {
  const value = new URLSearchParams(window.location.hash.slice(1)).get("section") as Section | null;
  return sections.some((item) => item.id === value) ? value! : "overview";
}

function writeSectionHash(section: Section) {
  const params = new URLSearchParams(window.location.hash.slice(1));
  params.set("section", section);
  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#${params.toString()}`);
}

function App() {
  const [section, setSection] = useState<Section>(() => sectionFromHash());
  const [collapsed, setCollapsed] = useState(() => window.localStorage.getItem("admin-nav-collapsed") === "1");
  const [query, setQuery] = useState("");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement | null>(null);
  const contentRef = useRef<HTMLElement | null>(null);
  const session = useData(() => api<SessionInfo>("/session"), []);
  const current = useMemo(() => sections.find((item) => item.id === section), [section]);
  const visibleSections = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("ru-RU");
    return normalized
      ? sections.filter((item) => `${item.label} ${item.description}`.toLocaleLowerCase("ru-RU").includes(normalized))
      : sections;
  }, [query]);

  useEffect(() => initializeTelegram(), []);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen(true);
      }
      if (event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey) {
        const target = event.target as HTMLElement | null;
        if (!target?.matches("input, textarea, select, [contenteditable='true']")) {
          event.preventDefault();
          searchRef.current?.focus();
        }
      }
    };
    const onHashChange = () => setSection(sectionFromHash());
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("hashchange", onHashChange);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("hashchange", onHashChange);
    };
  }, []);
  useEffect(() => {
    writeSectionHash(section);
    contentRef.current?.focus({ preventScroll: true });
  }, [section]);
  useEffect(() => window.localStorage.setItem("admin-nav-collapsed", collapsed ? "1" : "0"), [collapsed]);

  if (session.loading) return <main className="boot"><Loading label="Проверяем административный доступ…"/></main>;
  if (session.error || !session.data) {
    return <main className="boot"><div className="denied"><Icon name="shield" size={34}/><h1>Доступ запрещён</h1><p>{session.error || "Этот Telegram-аккаунт не имеет доступа."}</p></div></main>;
  }

  const navigate = (target: Section) => {
    setSection(target);
    setPaletteOpen(false);
  };
  const views: Record<Section, React.ReactNode> = {
    overview: <OperationsOverview onNavigate={navigate}/>,
    catalog: <CatalogStudioView/>,
    users: <UsersWorkbenchView/>,
    suggestions: <SuggestionsWorkbenchView/>,
    community: <CommunityWorkbenchView/>,
    boosty: <BoostyWorkbenchView/>,
    broadcasts: <BroadcastsView/>,
    channel: <ChannelWorkbenchView/>,
    files: <FilesWorkbenchView/>,
    audit: <AuditWorkbenchView/>,
    settings: <SettingsWorkbenchView/>,
  };

  return <>
    <a className="skip-link" href="#admin-content">Перейти к содержимому</a>
    <div className={`shell${collapsed ? " collapsed" : ""}`}>
      <aside aria-label="Основная навигация">
        <div className="brand-row">
          <div className="brand"><span><Icon name="book" size={22}/></span><div><b>Dollar TL</b><small>Operations Center</small></div></div>
          <button className="collapse-button" aria-label={collapsed ? "Развернуть меню" : "Свернуть меню"} aria-expanded={!collapsed} onClick={() => setCollapsed((value) => !value)}><Icon name="menu"/></button>
        </div>
        <label className="nav-search"><Icon name="search"/><input ref={searchRef} value={query} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)} placeholder="Фильтр разделов" aria-label="Фильтр разделов"/><kbd>/</kbd></label>
        <nav aria-label="Разделы панели">
          {visibleSections.map((item) => <button className={item.id === section ? "active" : ""} key={item.id} onClick={() => navigate(item.id)} title={collapsed ? item.label : undefined} aria-current={item.id === section ? "page" : undefined}><span className="nav-icon"><Icon name={item.icon}/></span><span className="nav-copy"><strong>{item.label}</strong><small>{item.description}</small></span></button>)}
          {!visibleSections.length && <div className="nav-empty" role="status">Ничего не найдено</div>}
        </nav>
        <div className="admin-card"><span><Icon name="shield"/></span><div><strong>{session.data.first_name || "Администратор"}</strong><small>{session.data.username ? `@${session.data.username}` : session.data.telegram_id}</small></div></div>
      </aside>
      <main id="admin-content" ref={contentRef} tabIndex={-1} aria-label={current?.label}>
        <header className="workspace"><div><span><Icon name={current?.icon || "dashboard"}/></span><div><strong>{current?.label}</strong><small>{current?.description}</small></div></div><div className="workspace-actions"><button className="workspace-command" onClick={() => setPaletteOpen(true)}><span><Icon name="search"/><span>Глобальный поиск</span></span><kbd>Ctrl K</kbd></button><em><i/>Production</em></div></header>
        <div className="mobile-head"><div><Icon name={current?.icon || "dashboard"}/><b>{current?.label}</b></div><button className="mobile-command" aria-label="Глобальный поиск" onClick={() => setPaletteOpen(true)}><Icon name="search"/></button><select aria-label="Раздел панели" value={section} onChange={(event: React.ChangeEvent<HTMLSelectElement>) => navigate(event.target.value as Section)}>{sections.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></div>
        {views[section]}
      </main>
    </div>
    <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onNavigate={navigate}/>
  </>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><ToastProvider><App/></ToastProvider></React.StrictMode>,
);
