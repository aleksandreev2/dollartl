import { api, confirmAction } from "./api";
import type { CatalogModal, CleanupPreview, DataState, FailedPublication, FileVersion, Preview, ReasonAction, Release, ReleaseDetail } from "./catalog-studio-types";

type Context = {
  release: DataState<ReleaseDetail>;
  failed: DataState<FailedPublication[]>;
  setModal: (modal: CatalogModal) => void;
  setBusy: (busy: boolean) => void;
  setFailedSelected: (ids: string[]) => void;
  push: (message: string, tone?: "success" | "error" | "info") => void;
};

function operationKey(prefix: string) {
  return `${prefix}:${Date.now()}:${crypto.randomUUID()}`;
}

export function catalogFileActions(context: Context) {
  const fail = (cause: unknown) => context.push(cause instanceof Error ? cause.message : String(cause), "error");
  const ask = (action: ReasonAction) => context.setModal({ kind: "reason", action });

  async function upload(item: Release, kind: string, file: File) {
    const body = new FormData(); body.set("file", file);
    context.setBusy(true);
    try {
      await api(`/catalog/releases/${item.id}/files/${kind}`, { method: "POST", body });
      await context.release.reload();
      context.push(`${kind.toUpperCase()} загружен новой версией.`, "success");
    } catch (cause) { fail(cause); } finally { context.setBusy(false); }
  }

  function activate(item: FileVersion) {
    ask({
      title: `Активация ${item.file_kind.toUpperCase()} v${item.version}`,
      description: "Остальные версии формата станут неактивными, inspection report и validation будут пересчитаны.",
      confirmLabel: "Активировать версию",
      run: async (reason) => {
        await api(`/catalog/file-versions/${item.id}/activate`, { method: "POST", body: JSON.stringify({ reason }) });
        await context.release.reload();
        context.push("Версия файла активирована.", "success");
      },
    });
  }

  async function preview(kind: "titles" | "releases", id: string, title: string) {
    try {
      context.setModal({ kind: "preview", title, data: await api<Preview>(`/catalog/${kind}/${id}/preview`) });
    } catch (cause) { fail(cause); }
  }

  async function cleanupPreview() {
    const key = operationKey("cleanup");
    context.setBusy(true);
    try {
      const data = await api<CleanupPreview>("/catalog/files/cleanup", { method: "POST", body: JSON.stringify({ dry_run: true, min_age_days: 30, idempotency_key: key }) });
      context.setModal({ kind: "cleanup", data, key });
    } catch (cause) { fail(cause); } finally { context.setBusy(false); }
  }

  async function cleanupExecute(data: CleanupPreview, key: string) {
    if (!(await confirmAction(`Удалить ${data.candidate_count} неиспользуемых версий?`))) return;
    context.setBusy(true);
    try {
      const result = await api<{ deleted_count: number; failed_count: number }>("/catalog/files/cleanup", {
        method: "POST",
        body: JSON.stringify({ dry_run: false, min_age_days: 30, idempotency_key: key, confirmation: data.confirmation }),
      });
      context.setModal(null);
      context.push(`Удалено ${result.deleted_count}, ошибок ${result.failed_count}.`, result.failed_count ? "info" : "success");
    } catch (cause) { fail(cause); } finally { context.setBusy(false); }
  }

  async function retryFailed(ids: string[]) {
    if (!ids.length) return;
    const key = operationKey("retry-publications");
    context.setBusy(true);
    try {
      const check = await api<{ eligible: number }>("/catalog/channel/retry-failed", { method: "POST", body: JSON.stringify({ publication_ids: ids, dry_run: true, idempotency_key: key }) });
      if (!(await confirmAction(`Вернуть в очередь ${check.eligible} публикаций?`))) return;
      const result = await api<{ retried: number }>("/catalog/channel/retry-failed", { method: "POST", body: JSON.stringify({ publication_ids: ids, dry_run: false, idempotency_key: key }) });
      context.setFailedSelected([]);
      await context.failed.reload();
      context.push(`В очередь возвращено: ${result.retried}.`, "success");
    } catch (cause) { fail(cause); } finally { context.setBusy(false); }
  }

  return { upload, activate, preview, cleanupPreview, cleanupExecute, retryFailed };
}
