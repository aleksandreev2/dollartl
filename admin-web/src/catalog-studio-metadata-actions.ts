import type { FormEvent } from "react";
import { api } from "./api";
import type { CatalogModal, DataState, ReasonAction, Release, ReleaseDetail, Revision, Title, TitleDetail, TitlePage } from "./catalog-studio-types";

type Context = {
  list: DataState<TitlePage>;
  detail: DataState<TitleDetail>;
  release: DataState<ReleaseDetail>;
  setModal: (modal: CatalogModal) => void;
  setBusy: (busy: boolean) => void;
  setSelectedTitle: (id: string | null) => void;
  setSelectedRelease: (id: string | null) => void;
  refresh: () => Promise<void>;
  push: (message: string, tone?: "success" | "error" | "info") => void;
};

export function catalogMetadataActions(context: Context) {
  const fail = (cause: unknown) => context.push(cause instanceof Error ? cause.message : String(cause), "error");
  const ask = (action: ReasonAction) => context.setModal({ kind: "reason", action });

  async function createTitle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    context.setBusy(true);
    try {
      const item = await api<Title>("/titles", { method: "POST", body: JSON.stringify({
        english_title: form.get("english_title"), original_title: form.get("original_title"),
        original_language: form.get("original_language"), publication_status: form.get("publication_status"),
        description: form.get("description") || "", boosty_url: form.get("boosty_url") || null,
        aliases: String(form.get("aliases") || "").split("\n").map((value) => value.trim()).filter(Boolean),
      }) });
      context.setModal(null);
      context.setSelectedTitle(item.id);
      await context.list.reload();
      context.push("Тайтл создан.", "success");
    } catch (cause) { fail(cause); } finally { context.setBusy(false); }
  }

  async function createRelease(event: FormEvent<HTMLFormElement>, title: Title) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    context.setBusy(true);
    try {
      const item = await api<Release>("/releases", { method: "POST", body: JSON.stringify({
        title_id: title.id, chapter_start: Number(form.get("chapter_start")), chapter_end: Number(form.get("chapter_end")),
        display_name: form.get("display_name") || null, boosty_url: form.get("boosty_url") || null,
      }) });
      context.setModal(null);
      context.setSelectedRelease(item.id);
      await context.detail.reload();
      context.push("Пакет создан.", "success");
    } catch (cause) { fail(cause); } finally { context.setBusy(false); }
  }

  async function saveTitle(event: FormEvent<HTMLFormElement>, item: Title) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    context.setBusy(true);
    try {
      await api(`/catalog/titles/${item.id}`, { method: "PUT", body: JSON.stringify({
        slug: form.get("slug"), english_title: form.get("english_title"), original_title: form.get("original_title"),
        original_language: form.get("original_language"), publication_status: form.get("publication_status"),
        description: form.get("description") || "", boosty_url: form.get("boosty_url") || null,
        aliases: String(form.get("aliases") || "").split("\n").map((value) => value.trim()).filter(Boolean),
        reason: form.get("reason"), expected_updated_at: item.updated_at,
      }) });
      context.setModal(null);
      await context.refresh();
      context.push("Тайтл обновлён.", "success");
    } catch (cause) { fail(cause); } finally { context.setBusy(false); }
  }

  async function saveRelease(event: FormEvent<HTMLFormElement>, item: Release) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    context.setBusy(true);
    try {
      await api(`/catalog/releases/${item.id}`, { method: "PUT", body: JSON.stringify({
        chapter_start: Number(form.get("chapter_start")), chapter_end: Number(form.get("chapter_end")),
        display_name: form.get("display_name") || null, boosty_url: form.get("boosty_url") || null,
        comments_enabled: form.get("comments_enabled") === "on", reason: form.get("reason"),
        expected_updated_at: item.updated_at,
      }) });
      context.setModal(null);
      await context.refresh();
      context.push("Пакет обновлён.", "success");
    } catch (cause) { fail(cause); } finally { context.setBusy(false); }
  }

  function publication(kind: "titles" | "releases", item: Title | Release, published: boolean) {
    ask({
      title: published ? "Публикация" : "Снятие с публикации",
      description: published ? "Объект станет доступен в каталоге и получит активную deep link." : "Deep links будут отключены, а зависимые данные пересчитаны.",
      confirmLabel: published ? "Опубликовать" : "Снять с публикации", danger: !published,
      run: async (reason) => {
        await api(`/catalog/${kind}/${item.id}/publication`, { method: "POST", body: JSON.stringify({ published, reason, expected_updated_at: item.updated_at }) });
        await context.refresh();
        context.push(published ? "Опубликовано." : "Снято с публикации.", "success");
      },
    });
  }

  function rollback(kind: "titles" | "releases", id: string, revision: Revision, updatedAt: string) {
    const cover = kind === "titles" && Boolean(revision.snapshot?.cover_object_key);
    ask({
      title: `Rollback к revision ${revision.revision}`,
      description: cover ? "Будут восстановлены метаданные и обложка из snapshot. Текущее состояние сохранится новой revision." : "Текущее состояние сначала сохранится новой revision, поэтому rollback обратим.",
      confirmLabel: cover ? "Восстановить тайтл и обложку" : "Восстановить revision", danger: true,
      run: async (reason) => {
        await api(`/catalog/${kind}/${id}/rollback/${revision.id}`, { method: "POST", body: JSON.stringify({ reason, expected_updated_at: updatedAt }) });
        await context.refresh();
        context.push("Версия восстановлена.", "success");
      },
    });
  }

  function replaceCover(item: Title, file: File) {
    ask({
      title: "Замена обложки",
      description: "Старая обложка останется в snapshot revision и сможет быть восстановлена через историю тайтла.",
      confirmLabel: "Загрузить новую обложку",
      run: async (reason) => {
        const body = new FormData(); body.set("file", file);
        await api(`/catalog/titles/${item.id}/cover?expected_updated_at=${encodeURIComponent(item.updated_at)}&reason=${encodeURIComponent(reason)}`, { method: "POST", body });
        await context.refresh();
        context.push("Обложка обновлена. Предыдущая версия доступна через rollback.", "success");
      },
    });
  }

  return { createTitle, createRelease, saveTitle, saveRelease, publication, rollback, replaceCover };
}
