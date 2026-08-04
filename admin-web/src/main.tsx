import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import { api, initializeTelegram } from "./api";
import type { SessionInfo } from "./types";
import { Icon, Loading, sections, useData, type Section } from "./admin-ui";
import {
  BroadcastsView,
  CatalogView,
  CommunityView,
  SuggestionsView,
  UsersView,
} from "./admin-views";
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

function App() {
  const [section, setSection] = useState<Section>("overview");
  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement | null>(null);
  const session = useData(() => api<SessionInfo>("/session"), []);
  const current = useMemo(
    () => sections.find((item) => item.id === section),
    [section],
  );
  const visibleSections = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("ru-RU");
    return normalized
      ? sections.filter((item) =>
          `${item.label} ${item.description}`
            .toLocaleLowerCase("ru-RU")
            .includes(normalized),
        )
      : sections;
  }, [query]);

  useEffect(() => initializeTelegram(), []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  if (session.loading) {
    return (
      <main className="boot">
        <Loading />
        <p>Проверяем административный доступ…</p>
      </main>
    );
  }

  if (session.error || !session.data) {
    return (
      <main className="boot">
        <div className="denied">
          <Icon name="shield" size={34} />
          <h1>Доступ запрещён</h1>
          <p>{session.error || "Этот Telegram-аккаунт не имеет доступа."}</p>
        </div>
      </main>
    );
  }

  const navigate = (target: Section) => {
    setSection(target);
    setPaletteOpen(false);
  };

  const views: Record<Section, React.ReactNode> = {
    overview: <OperationsOverview onNavigate={navigate} />,
    catalog: <CatalogView />,
    users: <UsersView />,
    suggestions: <SuggestionsView />,
    community: <CommunityView />,
    boosty: <BoostyWorkbenchView />,
    broadcasts: <BroadcastsView />,
    channel: <ChannelWorkbenchView />,
    files: <FilesWorkbenchView />,
    audit: <AuditWorkbenchView />,
    settings: <SettingsWorkbenchView />,
  };

  return (
    <>
      <div className={`shell${collapsed ? " collapsed" : ""}`}>
        <aside>
          <div className="brand-row">
            <div className="brand">
              <span>
                <Icon name="book" size={22} />
              </span>
              <div>
                <b>Dollar TL</b>
                <small>Operations Center</small>
              </div>
            </div>
            <button
              className="collapse-button"
              aria-label="Свернуть меню"
              onClick={() => setCollapsed((value) => !value)}
            >
              <Icon name="menu" />
            </button>
          </div>

          <label className="nav-search">
            <Icon name="search" />
            <input
              ref={searchRef}
              value={query}
              onChange={(event: React.ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)}
              placeholder="Фильтр разделов"
            />
          </label>

          <nav>
            {visibleSections.map((item) => (
              <button
                className={item.id === section ? "active" : ""}
                key={item.id}
                onClick={() => navigate(item.id)}
                title={collapsed ? item.label : undefined}
              >
                <span className="nav-icon">
                  <Icon name={item.icon} />
                </span>
                <span className="nav-copy">
                  <strong>{item.label}</strong>
                  <small>{item.description}</small>
                </span>
              </button>
            ))}
            {!visibleSections.length && (
              <div className="nav-empty">Ничего не найдено</div>
            )}
          </nav>

          <div className="admin-card">
            <span>
              <Icon name="shield" />
            </span>
            <div>
              <strong>{session.data.first_name || "Администратор"}</strong>
              <small>
                {session.data.username
                  ? `@${session.data.username}`
                  : session.data.telegram_id}
              </small>
            </div>
          </div>
        </aside>

        <main>
          <header className="workspace">
            <div>
              <span>
                <Icon name={current?.icon || "dashboard"} />
              </span>
              <div>
                <strong>{current?.label}</strong>
                <small>{current?.description}</small>
              </div>
            </div>

            <div className="workspace-actions">
              <button
                className="workspace-command"
                onClick={() => setPaletteOpen(true)}
              >
                <span>
                  <Icon name="search" />
                  <span>Глобальный поиск</span>
                </span>
                <kbd>Ctrl K</kbd>
              </button>
              <em>
                <i />
                Production
              </em>
            </div>
          </header>

          <div className="mobile-head">
            <div>
              <Icon name={current?.icon || "dashboard"} />
              <b>{current?.label}</b>
            </div>
            <button
              className="mobile-command"
              aria-label="Глобальный поиск"
              onClick={() => setPaletteOpen(true)}
            >
              <Icon name="search" />
            </button>
            <select
              value={section}
              onChange={(event: React.ChangeEvent<HTMLSelectElement>) =>
                navigate(event.target.value as Section)
              }
            >
              {sections.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>

          {views[section]}
        </main>
      </div>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onNavigate={navigate}
      />
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
