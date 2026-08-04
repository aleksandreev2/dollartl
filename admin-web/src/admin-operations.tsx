import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import type { Overview } from "./types";
import {
  Badge,
  ErrorBox,
  Header,
  Icon,
  Loading,
  type IconName,
  type Section,
  useData,
} from "./admin-ui";

type AttentionSeverity = "critical" | "high" | "medium" | "low";

type AttentionItem = {
  id: string;
  kind: string;
  entity_id: string;
  severity: AttentionSeverity;
  title: string;
  description: string;
  section: Section;
  status?: string | null;
  created_at?: string | null;
  metadata: Record<string, unknown>;
};

type AttentionResponse = {
  items: AttentionItem[];
  counts: Record<AttentionSeverity, number>;
  total: number;
};

type SearchItem = {
  id: string;
  kind: string;
  entity_id: string;
  title: string;
  subtitle: string;
  section: Section;
  status?: string | null;
  created_at?: string | null;
  rank: number;
};

type SearchResponse = {
  query: string;
  items: SearchItem[];
  total: number;
};

const metricCards: Array<[keyof Overview, string, IconName]> = [
  ["users", "Пользователи", "users"],
  ["active_vip", "Активные VIP", "diamond"],
  ["grace", "Grace", "history"],
  ["published_titles", "Тайтлы", "book"],
  ["releases", "Пакеты", "folder"],
  ["suggestions_pending", "Заявки", "sparkles"],
  ["reports_open", "Жалобы", "alert"],
  ["ratings_new", "Оценки", "message"],
  ["active_bans", "Баны", "shield"],
  ["broadcasts_running", "Рассылки", "send"],
  ["boosty_errors", "Ошибки Boosty", "diamond"],
];

const quickActions: Array<[Section, string, string, IconName]> = [
  ["suggestions", "Проверить предложения", "Заявки и raw-файлы", "sparkles"],
  ["community", "Разобрать обратную связь", "Жалобы, оценки и комментарии", "message"],
  ["catalog", "Добавить публикацию", "Тайтл, пакет, PDF и EPUB", "book"],
  ["broadcasts", "Создать рассылку", "Текст, фото и аудитория", "send"],
];

const kindIcons: Record<string, IconName> = {
  title: "book",
  release: "folder",
  user: "users",
  suggestion: "sparkles",
  report: "alert",
  rating: "message",
  boosty_error: "diamond",
  broadcast: "send",
  channel_publication: "telegram",
  backup: "shield",
  release_validation: "folder",
  file: "folder",
  audit: "history",
};

function relativeDate(value?: string | null): string {
  if (!value) return "без даты";
  const date = new Date(value);
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return "только что";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} мин назад`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} ч назад`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)} дн назад`;
  return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium" }).format(date);
}

export function OperationsOverview({
  onNavigate,
}: {
  onNavigate: (section: Section) => void;
}) {
  const metrics = useData(() => api<Overview>("/overview"), []);
  const attention = useData(() => api<AttentionResponse>("/attention?limit=60"), []);

  async function reloadAll() {
    await Promise.all([metrics.reload(), attention.reload()]);
  }

  return (
    <section className="page operations-overview">
      <Header
        title="Операционный центр"
        description="Метрики, очередь внимания и быстрые действия в одном месте."
        action={
          <button className="with-icon" onClick={reloadAll}>
            <Icon name="refresh" />
            Обновить всё
          </button>
        }
      />

      {(metrics.error || attention.error) && (
        <ErrorBox text={metrics.error || attention.error} />
      )}

      {metrics.loading || !metrics.data ? (
        <Loading />
      ) : (
        <div className="metrics">
          {metricCards.map(([key, label, icon]) => (
            <article key={String(key)}>
              <span className="metric-icon">
                <Icon name={icon} />
              </span>
              <div>
                <span>{label}</span>
                <strong>{Number(metrics.data?.[key] || 0)}</strong>
              </div>
            </article>
          ))}
        </div>
      )}

      <div className="operations-grid">
        <div>
          <div className="section-heading">
            <div>
              <h2>Требует внимания</h2>
              <p>Сначала критические ошибки, затем незакрытые рабочие очереди.</p>
            </div>
            {attention.data && (
              <div className="attention-counts" aria-label="Сводка очереди">
                {(["critical", "high", "medium", "low"] as AttentionSeverity[]).map(
                  (severity) =>
                    attention.data!.counts[severity] > 0 && (
                      <span key={severity} className={`severity severity-${severity}`}>
                        {attention.data!.counts[severity]}
                      </span>
                    ),
                )}
              </div>
            )}
          </div>

          {attention.loading ? (
            <Loading />
          ) : !attention.data?.items.length ? (
            <div className="empty-state">
              <span>
                <Icon name="shield" size={24} />
              </span>
              <div>
                <strong>Открытых проблем нет</strong>
                <p>Новые ошибки и рабочие очереди появятся здесь автоматически.</p>
              </div>
            </div>
          ) : (
            <div className="attention-list">
              {attention.data.items.map((item) => (
                <button
                  key={item.id}
                  className="attention-item"
                  onClick={() => onNavigate(item.section)}
                >
                  <span className={`attention-icon severity-${item.severity}`}>
                    <Icon name={kindIcons[item.kind] || "alert"} />
                  </span>
                  <span className="attention-copy">
                    <span>
                      <strong>{item.title}</strong>
                      <em className={`severity-text severity-${item.severity}`}>
                        {item.severity}
                      </em>
                    </span>
                    <small>{item.description}</small>
                    <time>{relativeDate(item.created_at)}</time>
                  </span>
                  <Icon name="chevron" />
                </button>
              ))}
            </div>
          )}
        </div>

        <aside className="operations-actions">
          <div className="section-heading">
            <div>
              <h2>Быстрые действия</h2>
              <p>Частые рабочие сценарии.</p>
            </div>
          </div>
          <div className="quick-grid vertical">
            {quickActions.map(([target, title, description, icon]) => (
              <button
                key={target}
                className="quick-action"
                onClick={() => onNavigate(target)}
              >
                <span>
                  <Icon name={icon} />
                </span>
                <div>
                  <strong>{title}</strong>
                  <small>{description}</small>
                </div>
                <Icon name="chevron" />
              </button>
            ))}
          </div>
        </aside>
      </div>
    </section>
  );
}

type PaletteItem = {
  id: string;
  section: Section;
  title: string;
  subtitle: string;
  icon: IconName;
  status?: string | null;
};

const paletteActions: PaletteItem[] = [
  { id: "create-title", section: "catalog", title: "Создать тайтл или пакет", subtitle: "Открыть каталог и формы публикации", icon: "book" },
  { id: "review-suggestions", section: "suggestions", title: "Проверить предложения", subtitle: "Открыть очередь заявок", icon: "sparkles" },
  { id: "review-community", section: "community", title: "Разобрать жалобы и оценки", subtitle: "Открыть модерацию", icon: "message" },
  { id: "create-broadcast", section: "broadcasts", title: "Создать рассылку", subtitle: "Открыть редактор рассылок", icon: "send" },
  { id: "check-files", section: "files", title: "Проверить файлы и кэш", subtitle: "Открыть версии PDF/EPUB", icon: "folder" },
  { id: "open-audit", section: "audit", title: "Открыть журнал действий", subtitle: "Найти административную операцию", icon: "history" },
];

export function CommandPalette({
  open,
  onClose,
  onNavigate,
}: {
  open: boolean;
  onClose: () => void;
  onNavigate: (section: Section) => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(0);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setResponse(null);
    setError("");
    setSelected(0);
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const normalized = query.trim();
    if (normalized.length < 2) {
      setResponse(null);
      setLoading(false);
      setError("");
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setError("");
      try {
        const result = await api<SearchResponse>(
          `/search?q=${encodeURIComponent(normalized)}&limit=50`,
          { signal: controller.signal },
        );
        setResponse(result);
        setSelected(0);
      } catch (cause) {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : String(cause));
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 180);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [open, query]);

  const visible = useMemo<PaletteItem[]>(
    () =>
      query.trim().length < 2
        ? paletteActions
        : (response?.items || []).map((item) => ({
            id: item.id,
            section: item.section,
            title: item.title,
            subtitle: item.subtitle,
            icon: kindIcons[item.kind] || ("search" as IconName),
            status: item.status,
          })),
    [query, response],
  );

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      } else if (event.key === "ArrowDown") {
        event.preventDefault();
        setSelected((value) => Math.min(value + 1, Math.max(visible.length - 1, 0)));
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        setSelected((value) => Math.max(value - 1, 0));
      } else if (event.key === "Enter" && visible[selected]) {
        event.preventDefault();
        onNavigate(visible[selected].section);
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose, onNavigate, selected, visible]);

  if (!open) return null;

  return (
    <div className="command-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="command-palette"
        role="dialog"
        aria-modal="true"
        aria-label="Глобальный поиск"
        onMouseDown={(event: React.MouseEvent<HTMLElement>) => event.stopPropagation()}
      >
        <label className="command-input">
          <Icon name="search" size={21} />
          <input
            ref={inputRef}
            value={query}
            onChange={(event: React.ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)}
            placeholder="Тайтл, Anonymous ID, Telegram ID, файл, жалоба…"
          />
          <kbd>Esc</kbd>
        </label>

        <div className="command-meta">
          <span>
            {query.trim().length < 2
              ? "Быстрые команды"
              : loading
                ? "Ищем…"
                : `Найдено: ${response?.total || 0}`}
          </span>
          <small>↑ ↓ выбор · Enter открыть</small>
        </div>

        {error && <ErrorBox text={error} />}

        <div className="command-results">
          {visible.map((item, index) => (
            <button
              key={item.id}
              className={index === selected ? "selected" : ""}
              onMouseEnter={() => setSelected(index)}
              onClick={() => {
                onNavigate(item.section);
                onClose();
              }}
            >
              <span className="command-result-icon">
                <Icon name={item.icon} />
              </span>
              <span>
                <strong>{item.title}</strong>
                <small>{item.subtitle}</small>
              </span>
              {item.status ? <Badge value={item.status} /> : null}
              <Icon name="chevron" />
            </button>
          ))}
          {!loading && query.trim().length >= 2 && !visible.length && (
            <div className="command-empty">
              <Icon name="search" size={24} />
              <strong>Ничего не найдено</strong>
              <small>Попробуйте название, Anonymous ID, username или UUID.</small>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
