import { api } from "./api";

interface BackupItem {
  id: string;
  status: string;
  trigger_type: string;
  created_at: string;
  completed_at?: string | null;
  encrypted_size_bytes?: number | null;
  database_archive_verified: boolean;
  restore_verified: boolean;
  storage_replication_verified: boolean;
  telegram_delivery_status: string;
  database_available: boolean;
  manifest_available: boolean;
  error?: string | null;
}

interface ResilienceStatus {
  backup_enabled: boolean;
  backup_replication_enabled: boolean;
  backup_interval_hours: number;
  backup_retention_count: number;
  backup_retention_days: number;
  dependencies: Record<string, { ok?: boolean; error?: string; [key: string]: unknown }>;
  services: Array<{
    service_name: string;
    instance_id: string;
    status: string;
    last_seen_at: string;
    stale: boolean;
    metadata: Record<string, unknown>;
  }>;
}

const ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  "'": "&#39;",
  '"': "&quot;",
};

function escapeHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ESCAPES[character] || character);
}

function formatBytes(value?: number | null): string {
  if (!value) return "—";
  const units = ["Б", "КБ", "МБ", "ГБ"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index ? 1 : 0)} ${units[index]}`;
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusClass(value: string | boolean): string {
  if (value === true || ["succeeded", "healthy", "sent", "linked"].includes(String(value))) {
    return "res-ok";
  }
  if (["queued", "running", "pending", "degraded"].includes(String(value))) {
    return "res-warn";
  }
  return "res-bad";
}

async function openLink(path: string): Promise<void> {
  const payload = await api<{ url: string; filename?: string }>(path);
  const anchor = document.createElement("a");
  anchor.href = payload.url;
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  if (payload.filename) anchor.download = payload.filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

async function render(container: HTMLElement): Promise<void> {
  container.innerHTML = '<div class="res-loading">Проверяем сервисы и резервные копии…</div>';
  try {
    const [health, backups] = await Promise.all([
      api<ResilienceStatus>("/resilience"),
      api<BackupItem[]>("/backups?limit=50"),
    ]);
    const dependencies = Object.entries(health.dependencies)
      .map(([name, value]) => `
        <div class="res-row">
          <span>${escapeHtml(name)}</span>
          <b class="${statusClass(Boolean(value.ok))}">${value.ok ? "OK" : escapeHtml(value.error || "ошибка")}</b>
        </div>`)
      .join("");
    const services = health.services.length
      ? health.services.map((service) => `
        <div class="res-service">
          <div><strong>${escapeHtml(service.service_name)}</strong><small>${escapeHtml(service.instance_id)}</small></div>
          <div><b class="${statusClass(service.stale ? "stale" : service.status)}">${service.stale ? "устарел" : escapeHtml(service.status)}</b><small>${formatDate(service.last_seen_at)}</small></div>
        </div>`).join("")
      : '<div class="res-loading">Heartbeat ещё не зарегистрирован.</div>';
    const backupRows = backups.length
      ? backups.map((backup) => `
        <article class="res-backup">
          <div class="res-backup-head"><strong>${formatDate(backup.created_at)}</strong><b class="${statusClass(backup.status)}">${escapeHtml(backup.status)}</b></div>
          <small>${escapeHtml(backup.trigger_type)} · ${formatBytes(backup.encrypted_size_bytes)} · Telegram: ${escapeHtml(backup.telegram_delivery_status)}</small>
          <div class="res-checks">
            <span class="${statusClass(backup.database_archive_verified)}">архив</span>
            <span class="${statusClass(backup.restore_verified)}">restore</span>
            <span class="${statusClass(backup.storage_replication_verified)}">S3 mirror</span>
          </div>
          ${backup.error ? `<p class="res-error">${escapeHtml(backup.error)}</p>` : ""}
          <div class="res-actions">
            ${backup.database_available ? `<button data-backup-download="${backup.id}">Скачать</button>` : ""}
            ${backup.manifest_available ? `<button data-backup-manifest="${backup.id}">Manifest</button>` : ""}
          </div>
        </article>`).join("")
      : '<div class="res-loading">Запусков backup пока нет.</div>';
    container.innerHTML = `
      <section class="res-section">
        <div class="res-summary">
          <div><span>Автоматические backup</span><b class="${statusClass(health.backup_enabled)}">${health.backup_enabled ? "включены" : "выключены"}</b></div>
          <div><span>S3 replication</span><b class="${statusClass(health.backup_replication_enabled)}">${health.backup_replication_enabled ? "включена" : "выключена"}</b></div>
          <div><span>Интервал / хранение</span><b>${health.backup_interval_hours} ч · ${health.backup_retention_count} копий / ${health.backup_retention_days} дней</b></div>
        </div>
        <button class="res-primary" data-trigger-backup>Создать backup сейчас</button>
      </section>
      <section class="res-section"><h3>Зависимости</h3>${dependencies}</section>
      <section class="res-section"><h3>Сервисы</h3>${services}</section>
      <section class="res-section"><h3>История backup</h3><div class="res-backups">${backupRows}</div></section>`;

    container.querySelector<HTMLButtonElement>("[data-trigger-backup]")?.addEventListener("click", async (event) => {
      const button = event.currentTarget as HTMLButtonElement;
      button.disabled = true;
      try {
        await api("/backups/trigger", { method: "POST" });
        await render(container);
      } catch (cause) {
        window.alert(cause instanceof Error ? cause.message : String(cause));
        button.disabled = false;
      }
    });
    container.querySelectorAll<HTMLButtonElement>("[data-backup-download]").forEach((button) => {
      button.addEventListener("click", () => void openLink(`/backups/${button.dataset.backupDownload}/download`));
    });
    container.querySelectorAll<HTMLButtonElement>("[data-backup-manifest]").forEach((button) => {
      button.addEventListener("click", () => void openLink(`/backups/${button.dataset.backupManifest}/manifest`));
    });
  } catch (cause) {
    container.innerHTML = `<div class="res-error">${escapeHtml(cause instanceof Error ? cause.message : String(cause))}</div>`;
  }
}

function mount(): void {
  const style = document.createElement("style");
  style.textContent = `
    .res-launch{position:fixed;right:18px;bottom:72px;z-index:60;border:1px solid #4fa58a;border-radius:999px;background:#17654f;color:#fff;padding:11px 16px;box-shadow:0 12px 34px #0008;cursor:pointer}
    .res-drawer{position:fixed;display:block;inset:0 0 0 auto;z-index:80;width:min(520px,100%);background:#0d141d;border-left:1px solid #30443e;box-shadow:-20px 0 50px #0008;padding:18px;overflow:auto;transform:translateX(105%);transition:transform .2s ease}.res-drawer.open{transform:translateX(0)}
    .res-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.res-head h2{margin:0}.res-close,.res-section button{border:1px solid #3d5b51;border-radius:9px;background:#1b3029;color:#eef8f4;padding:8px 11px;cursor:pointer}.res-primary{width:100%;background:#17654f!important;border-color:#3f967a!important;margin-top:12px}
    .res-section{border:1px solid #283a35;border-radius:13px;background:#131d25;padding:13px;margin-bottom:11px}.res-section h3{margin:0 0 10px}.res-summary{display:grid;gap:8px}.res-summary>div,.res-row,.res-service,.res-backup-head{display:flex;justify-content:space-between;gap:10px}.res-row,.res-service{padding:8px 0;border-top:1px solid #25352f}.res-row:first-child{border-top:0}.res-service small{display:block;color:#91a79f;margin-top:3px;text-align:right}.res-backups{display:grid;gap:9px}.res-backup{border:1px solid #2a4038;border-radius:11px;background:#17242d;padding:11px}.res-backup>small{display:block;color:#9fb1ac;margin:6px 0}.res-checks,.res-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px}.res-checks span{border-radius:999px;padding:3px 7px;background:#26362f;font-size:12px}.res-ok{color:#83e1be}.res-warn{color:#efd081}.res-bad,.res-error{color:#ff9ca8}.res-loading,.res-error{padding:16px}
  `;
  document.head.appendChild(style);
  const launch = document.createElement("button");
  launch.className = "res-launch";
  launch.textContent = "Backup и health";
  const drawer = document.createElement("div");
  drawer.className = "res-drawer";
  drawer.innerHTML = '<div class="res-head"><div><h2>Надёжность</h2><small>Backup, сервисы и зависимости</small></div><button class="res-close">Закрыть</button></div><div class="res-content"></div>';
  document.body.append(launch, drawer);
  launch.addEventListener("click", () => {
    drawer.classList.add("open");
    void render(drawer.querySelector<HTMLElement>(".res-content")!);
  });
  drawer.querySelector(".res-close")?.addEventListener("click", () => drawer.classList.remove("open"));
}

window.addEventListener("DOMContentLoaded", mount);
