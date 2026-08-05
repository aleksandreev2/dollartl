import React, { FormEvent, useMemo, useState } from "react";
import { api } from "./api";
import { Icon, useToast } from "./admin-ui";
import type { PipelineAnalysis, Release, Title, TitleDetail } from "./catalog-studio-types";
import "./catalog-pipeline.css";

type PipelineProps = {
  onCancel: () => void;
  onComplete: (titleId: string) => Promise<void> | void;
  onOpenExisting: (titleId: string) => void;
};

type SelectedFiles = {
  pdf: File | null;
  epub: File | null;
  cover: File | null;
};

type Draft = {
  english_title: string;
  original_title: string;
  original_language: string;
  translation_language: string;
  publication_status: string;
  description: string;
  boosty_url: string;
  aliases: string;
  chapter_start: string;
  chapter_end: string;
  display_name: string;
};

type ProgressItem = {
  label: string;
  state: "waiting" | "running" | "done" | "error";
};

const LANGUAGE_OPTIONS = ["Korean", "Japanese", "Chinese", "English", "Russian", "Other"];

function initialDraft(analysis: PipelineAnalysis): Draft {
  const item = analysis.suggested;
  return {
    english_title: item.english_title || "",
    original_title: item.original_title || item.english_title || "",
    original_language: item.original_language || "",
    translation_language: item.translation_language || "Russian",
    publication_status: item.publication_status || "ongoing",
    description: item.description || "",
    boosty_url: item.boosty_url || "",
    aliases: (item.aliases || []).join("\n"),
    chapter_start: item.chapter_start === null ? "" : String(item.chapter_start),
    chapter_end: item.chapter_end === null ? "" : String(item.chapter_end),
    display_name: item.display_name || "",
  };
}

function confidenceLabel(value: string) {
  if (value === "high") return "Высокая";
  if (value === "medium") return "Средняя";
  return "Низкая";
}

function languageLabel(value?: string | null) {
  const labels: Record<string, string> = {
    Korean: "Корейский",
    Japanese: "Японский",
    Chinese: "Китайский",
    English: "Английский",
    Russian: "Русский",
    Other: "Другой",
  };
  return value ? labels[value] || value : "Не определён";
}

function fileRange(file: PipelineAnalysis["files"][number]) {
  const detected = file.chapter_detection;
  if (detected.chapter_start === null || detected.chapter_end === null) return "Диапазон не найден";
  const count = detected.chapter_end - detected.chapter_start + 1;
  return `Главы ${detected.chapter_start}–${detected.chapter_end} · ${count}`;
}

export function CatalogPipeline({ onCancel, onComplete, onOpenExisting }: PipelineProps) {
  const [step, setStep] = useState<"files" | "review" | "creating" | "done">("files");
  const [files, setFiles] = useState<SelectedFiles>({ pdf: null, epub: null, cover: null });
  const [analysis, setAnalysis] = useState<PipelineAnalysis | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState("");
  const [createdTitleId, setCreatedTitleId] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressItem[]>([]);
  const { push } = useToast();

  const canAnalyse = Boolean(files.pdf || files.epub);
  const chapterCount = useMemo(() => {
    if (!draft) return 0;
    const start = Number(draft.chapter_start);
    const end = Number(draft.chapter_end);
    return Number.isFinite(start) && Number.isFinite(end) && end >= start ? end - start + 1 : 0;
  }, [draft]);

  function choose(kind: keyof SelectedFiles, file: File | null) {
    setFiles((current) => ({ ...current, [kind]: file }));
    setError("");
  }

  async function analyse(event: FormEvent) {
    event.preventDefault();
    if (!canAnalyse) {
      setError("Добавьте PDF, EPUB или оба файла.");
      return;
    }
    setError("");
    const body = new FormData();
    if (files.pdf) body.set("pdf", files.pdf);
    if (files.epub) body.set("epub", files.epub);
    try {
      const result = await api<PipelineAnalysis>("/catalog/pipeline/analyze", { method: "POST", body });
      setAnalysis(result);
      setDraft(initialDraft(result));
      setStep("review");
      push("Файлы проверены. Просмотрите предложенные данные.", "success");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }

  function update(field: keyof Draft, value: string) {
    setDraft((current) => current ? { ...current, [field]: value } : current);
  }

  function validateDraft(): string | null {
    if (!draft?.english_title.trim()) return "Укажите название для каталога.";
    if (!draft.original_title.trim()) return "Укажите оригинальное название.";
    if (!draft.original_language.trim()) return "Выберите язык оригинала.";
    const start = Number(draft.chapter_start);
    const end = Number(draft.chapter_end);
    if (!Number.isInteger(start) || start < 0) return "Проверьте начальную главу.";
    if (!Number.isInteger(end) || end < start) return "Конечная глава должна быть не меньше начальной.";
    return null;
  }

  function setProgressState(index: number, state: ProgressItem["state"]) {
    setProgress((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, state } : item));
  }

  async function uploadCover(title: Title, file: File) {
    const detail = await api<TitleDetail>(`/catalog/titles/${title.id}`);
    const body = new FormData();
    body.set("file", file);
    await api(`/catalog/titles/${title.id}/cover?expected_updated_at=${encodeURIComponent(detail.title.updated_at)}&reason=${encodeURIComponent("Загрузка обложки при создании произведения")}`, {
      method: "POST",
      body,
    });
  }

  async function uploadReleaseFile(releaseId: string, kind: "pdf" | "epub", file: File) {
    const body = new FormData();
    body.set("file", file);
    await api(`/catalog/releases/${releaseId}/files/${kind}?reason=${encodeURIComponent("Первичная загрузка через конвейер публикации")}`, {
      method: "POST",
      body,
    });
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    const validation = validateDraft();
    if (validation || !draft) {
      setError(validation || "Проверьте данные.");
      return;
    }

    setStep("creating");
    setError("");
    const tasks: ProgressItem[] = [
      { label: "Создать карточку произведения", state: "waiting" },
      { label: "Создать первый пакет глав", state: "waiting" },
      ...(files.cover ? [{ label: "Загрузить обложку", state: "waiting" as const }] : []),
      ...(files.pdf ? [{ label: "Загрузить и проверить PDF", state: "waiting" as const }] : []),
      ...(files.epub ? [{ label: "Загрузить и проверить EPUB", state: "waiting" as const }] : []),
    ];
    setProgress(tasks);

    let title: Title | null = null;
    let release: Release | null = null;
    let taskIndex = 0;
    try {
      setProgressState(taskIndex, "running");
      title = await api<Title>("/titles", {
        method: "POST",
        body: JSON.stringify({
          english_title: draft.english_title.trim(),
          original_title: draft.original_title.trim(),
          original_language: draft.original_language.trim(),
          publication_status: draft.publication_status,
          description: draft.description.trim(),
          boosty_url: draft.boosty_url.trim() || null,
          aliases: draft.aliases.split("\n").map((value) => value.trim()).filter(Boolean),
        }),
      });
      setCreatedTitleId(title.id);
      setProgressState(taskIndex++, "done");

      setProgressState(taskIndex, "running");
      release = await api<Release>("/releases", {
        method: "POST",
        body: JSON.stringify({
          title_id: title.id,
          chapter_start: Number(draft.chapter_start),
          chapter_end: Number(draft.chapter_end),
          display_name: draft.display_name.trim() || null,
          boosty_url: draft.boosty_url.trim() || null,
        }),
      });
      setProgressState(taskIndex++, "done");

      if (files.cover) {
        setProgressState(taskIndex, "running");
        await uploadCover(title, files.cover);
        setProgressState(taskIndex++, "done");
      }
      if (files.pdf) {
        setProgressState(taskIndex, "running");
        await uploadReleaseFile(release.id, "pdf", files.pdf);
        setProgressState(taskIndex++, "done");
      }
      if (files.epub) {
        setProgressState(taskIndex, "running");
        await uploadReleaseFile(release.id, "epub", files.epub);
        setProgressState(taskIndex++, "done");
      }

      setStep("done");
      push("Черновик произведения и первый пакет готовы.", "success");
    } catch (cause) {
      setProgressState(taskIndex, "error");
      const message = cause instanceof Error ? cause.message : String(cause);
      setError(title
        ? `Черновик уже создан, но конвейер остановился: ${message}. Откройте карточку и продолжите с места остановки.`
        : message);
      setStep("creating");
    }
  }

  function reset() {
    setFiles({ pdf: null, epub: null, cover: null });
    setAnalysis(null);
    setDraft(null);
    setError("");
    setCreatedTitleId(null);
    setProgress([]);
    setStep("files");
  }

  return <section className="catalog-pipeline" aria-labelledby="pipeline-title">
    <header className="pipeline-header">
      <div>
        <button className="pipeline-back" type="button" onClick={onCancel}>← Вернуться в каталог</button>
        <p className="eyebrow">Конвейер публикации</p>
        <h1 id="pipeline-title">Добавить произведение</h1>
        <p>Загрузите готовые файлы. Система сама предложит название, язык, диапазон и количество глав, после чего соберёт черновик.</p>
      </div>
      <ol className="pipeline-steps" aria-label="Этапы создания">
        <li className={step === "files" ? "active" : "done"}><span>1</span><div><strong>Файлы</strong><small>PDF, EPUB, обложка</small></div></li>
        <li className={step === "review" ? "active" : step === "files" ? "" : "done"}><span>2</span><div><strong>Проверка</strong><small>Названия и главы</small></div></li>
        <li className={step === "creating" ? "active" : step === "done" ? "done" : ""}><span>3</span><div><strong>Сборка</strong><small>Карточка и пакет</small></div></li>
      </ol>
    </header>

    {error && <div className="pipeline-error" role="alert"><Icon name="alert"/><span>{error}</span></div>}

    {step === "files" && <form className="pipeline-panel" onSubmit={analyse}>
      <div className="pipeline-section-title"><div><p className="eyebrow">Шаг 1</p><h2>Добавьте материалы</h2></div><span>PDF и EPUB можно загрузить вместе</span></div>
      <div className="pipeline-upload-grid">
        <FileCard kind="pdf" title="PDF книги" description="Проверим заголовки, метаданные и диапазон глав." accept=".pdf,application/pdf" file={files.pdf} required onChange={(file) => choose("pdf", file)}/>
        <FileCard kind="epub" title="EPUB книги" description="Прочитаем метаданные, содержание и структуру глав." accept=".epub,application/epub+zip" file={files.epub} required onChange={(file) => choose("epub", file)}/>
        <FileCard kind="cover" title="Обложка" description="Необязательно. Можно добавить позже из карточки." accept="image/*" file={files.cover} onChange={(file) => choose("cover", file)}/>
      </div>
      <div className="pipeline-info"><Icon name="shield"/><div><strong>Пока ничего не создаётся</strong><span>На этом этапе файлы только временно анализируются. Запись в каталог появится после вашего подтверждения.</span></div></div>
      <footer className="pipeline-footer"><button type="button" onClick={onCancel}>Отмена</button><button className="primary" disabled={!canAnalyse}>Проверить файлы</button></footer>
    </form>}

    {step === "review" && analysis && draft && <form className="pipeline-review" onSubmit={create}>
      <div className="pipeline-analysis-column">
        <section className="pipeline-panel">
          <div className="pipeline-section-title"><div><p className="eyebrow">Результат анализа</p><h2>Что удалось определить</h2></div><span className={`pipeline-confidence ${analysis.confidence}`}>Уверенность: {confidenceLabel(analysis.confidence)}</span></div>
          <div className="pipeline-result-cards">
            <div><small>Название</small><strong>{analysis.suggested.english_title || "Не найдено"}</strong></div>
            <div><small>Язык текста файлов</small><strong>{languageLabel(analysis.suggested.translation_language)}</strong></div>
            <div><small>Диапазон</small><strong>{analysis.suggested.chapter_start === null ? "Не найден" : `${analysis.suggested.chapter_start}–${analysis.suggested.chapter_end}`}</strong></div>
            <div><small>Количество глав</small><strong>{analysis.suggested.chapter_count || "—"}</strong></div>
          </div>
          <div className="pipeline-file-results">{analysis.files.map((item) => <article key={item.kind}>
            <div className={`pipeline-file-icon ${item.kind}`}>{item.kind.toUpperCase()}</div>
            <div><strong>{item.filename}</strong><span>{fileRange(item)}</span><small>{item.title || "Название в метаданных не найдено"} · текст: {languageLabel(item.text_language || item.language)}</small></div>
            <span className="pipeline-source">{item.chapter_detection.source === "filename" ? "из имени файла" : "из содержимого"}</span>
          </article>)}</div>
          {analysis.warnings.length > 0 && <div className="pipeline-warnings"><strong>Нужно проверить вручную</strong>{analysis.warnings.map((warning) => <span key={warning}>• {warning}</span>)}</div>}
          {analysis.possible_duplicates.length > 0 && <div className="pipeline-duplicates"><strong>Похожие произведения уже есть</strong><p>Убедитесь, что не создаёте дубль.</p>{analysis.possible_duplicates.map((item) => <button type="button" key={item.id} onClick={() => onOpenExisting(item.id)}><span>{item.english_title}</span><small>{item.original_title}</small></button>)}</div>}
        </section>
      </div>

      <div className="pipeline-form-column">
        <section className="pipeline-panel pipeline-human-form">
          <div className="pipeline-section-title"><div><p className="eyebrow">Шаг 2</p><h2>Проверьте карточку</h2></div><span>Все поля можно исправить</span></div>
          <label className="wide">Название в каталоге<input value={draft.english_title} onChange={(event) => update("english_title", event.target.value)} required autoFocus/><small>Название, которое увидят пользователи в боте.</small></label>
          <label className="wide">Оригинальное название<input value={draft.original_title} onChange={(event) => update("original_title", event.target.value)} required/></label>
          <div className="pipeline-form-row">
            <label>Язык оригинала<select value={draft.original_language} onChange={(event) => update("original_language", event.target.value)} required><option value="">Выберите язык</option>{LANGUAGE_OPTIONS.map((item) => <option key={item} value={item}>{languageLabel(item)}</option>)}</select></label>
            <label>Состояние перевода<select value={draft.publication_status} onChange={(event) => update("publication_status", event.target.value)}><option value="ongoing">Перевод продолжается</option><option value="completed">Перевод завершён</option><option value="hiatus">Перевод на паузе</option></select></label>
          </div>
          <div className="pipeline-form-row">
            <label>Первая глава<input type="number" min="0" value={draft.chapter_start} onChange={(event) => update("chapter_start", event.target.value)} required/></label>
            <label>Последняя глава<input type="number" min="0" value={draft.chapter_end} onChange={(event) => update("chapter_end", event.target.value)} required/></label>
          </div>
          <div className="pipeline-count"><span>В первом пакете</span><strong>{chapterCount || "—"} глав</strong></div>
          <label className="wide">Название первого пакета<input value={draft.display_name} onChange={(event) => update("display_name", event.target.value)} placeholder={chapterCount ? `Главы ${draft.chapter_start}–${draft.chapter_end}` : "Будет создано автоматически"}/></label>
          <label className="wide">Другие названия<textarea rows={3} value={draft.aliases} onChange={(event) => update("aliases", event.target.value)} placeholder="По одному названию на строку"/><small>По ним пользователи смогут находить произведение.</small></label>
          <label className="wide">Ссылка на публикацию Boosty<input type="url" value={draft.boosty_url} onChange={(event) => update("boosty_url", event.target.value)} placeholder="Можно добавить позже"/></label>
          <label className="wide">Описание<textarea rows={6} value={draft.description} onChange={(event) => update("description", event.target.value)} placeholder="Краткое описание произведения"/></label>
          <div className="pipeline-language-note"><Icon name="shield"/><span>Язык загруженных файлов определён как <strong>{languageLabel(draft.translation_language)}</strong>. Он используется для проверки материалов.</span></div>
          <footer className="pipeline-footer"><button type="button" onClick={() => setStep("files")}>Заменить файлы</button><button className="primary">Создать черновик и загрузить файлы</button></footer>
        </section>
      </div>
    </form>}

    {(step === "creating" || step === "done") && <section className="pipeline-panel pipeline-progress">
      <div className="pipeline-section-title"><div><p className="eyebrow">{step === "done" ? "Готово" : "Шаг 3"}</p><h2>{step === "done" ? "Черновик собран" : "Собираем произведение"}</h2></div></div>
      <div className="pipeline-progress-list">{progress.map((item, index) => <div key={`${item.label}-${index}`} className={item.state}>
        <span className="pipeline-progress-state">{item.state === "done" ? "✓" : item.state === "error" ? "!" : item.state === "running" ? "…" : index + 1}</span>
        <strong>{item.label}</strong>
        <small>{item.state === "done" ? "Готово" : item.state === "error" ? "Требует внимания" : item.state === "running" ? "Выполняется" : "Ожидает"}</small>
      </div>)}</div>
      {step === "done" && <div className="pipeline-success"><Icon name="shield" size={28}/><div><strong>Произведение готово к финальной проверке</strong><span>Оно сохранено как черновик. Публикация выполняется отдельно из карточки после preview.</span></div></div>}
      <footer className="pipeline-footer">
        {step === "done" && <button type="button" onClick={reset}>Добавить ещё одно</button>}
        {createdTitleId && <button type="button" className="primary" onClick={() => onComplete(createdTitleId)}>Открыть готовую карточку</button>}
      </footer>
    </section>}
  </section>;
}

function FileCard({ kind, title, description, accept, file, required, onChange }:{
  kind: "pdf" | "epub" | "cover";
  title: string;
  description: string;
  accept: string;
  file: File | null;
  required?: boolean;
  onChange: (file: File | null) => void;
}) {
  return <label className={`pipeline-upload-card ${file ? "selected" : ""}`}>
    <input type="file" accept={accept} onChange={(event) => onChange(event.target.files?.[0] || null)}/>
    <span className={`pipeline-upload-symbol ${kind}`}>{kind === "cover" ? "IMG" : kind.toUpperCase()}</span>
    <div><strong>{file?.name || title}</strong><span>{file ? `${(file.size / 1024 / 1024).toFixed(1)} МБ` : description}</span>{required && !file && <small>Нужен хотя бы один формат книги</small>}</div>
    <button type="button" tabIndex={-1}>{file ? "Заменить" : "Выбрать"}</button>
  </label>;
}
