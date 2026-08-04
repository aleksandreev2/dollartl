import { api } from "./api";
import type { SuggestionItem } from "./types";

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character] || character);
}

async function openRaw(suggestionId: string): Promise<void> {
  const button = document.querySelector<HTMLButtonElement>(`[data-open-raw="${suggestionId}"]`);
  if (button) button.disabled = true;
  try {
    const payload = await api<{ url: string }>(`/suggestions/${suggestionId}/raw-link`);
    window.open(payload.url, "_blank", "noopener,noreferrer");
  } catch (cause) {
    window.alert(cause instanceof Error ? cause.message : String(cause));
  } finally {
    if (button) button.disabled = false;
  }
}

async function render(container: HTMLElement): Promise<void> {
  container.innerHTML = '<div class="raw-loading">Загрузка заявок…</div>';
  try {
    const items = await api<SuggestionItem[]>("/suggestions?status=all&limit=500");
    const available = items.filter((item) => item.raw_file?.validation_status === "valid");
    container.innerHTML = available.length
      ? available.map((item) => `
        <article class="raw-review-item">
          <div><strong>${escapeHtml(item.original_title || "Без названия")}</strong><small>${escapeHtml(item.raw_file?.filename || "raw")}</small></div>
          <button type="button" data-open-raw="${item.id}">Открыть raw</button>
        </article>`).join("")
      : '<div class="raw-loading">Валидных raw-файлов пока нет.</div>';
    container.querySelectorAll<HTMLButtonElement>("[data-open-raw]").forEach((button) => {
      button.addEventListener("click", () => void openRaw(button.dataset.openRaw || ""));
    });
  } catch (cause) {
    container.innerHTML = `<div class="raw-error">${escapeHtml(cause instanceof Error ? cause.message : String(cause))}</div>`;
  }
}

function mount(): void {
  const style = document.createElement("style");
  style.textContent = `
    .raw-review-launch{position:fixed;right:18px;bottom:18px;z-index:60;border:1px solid #758bf2;border-radius:999px;background:#5c74e8;color:#fff;padding:11px 16px;box-shadow:0 12px 34px #0008;cursor:pointer}
    .raw-review-drawer{position:fixed;inset:0 0 0 auto;z-index:70;width:min(430px,100%);background:#0f1520;border-left:1px solid #303b51;box-shadow:-20px 0 50px #0008;padding:18px;overflow:auto;transform:translateX(105%);transition:transform .2s ease}
    .raw-review-drawer.open{transform:translateX(0)}.raw-review-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.raw-review-head h2{margin:0}.raw-review-list{display:grid;gap:9px}
    .raw-review-item{display:flex;justify-content:space-between;gap:12px;align-items:center;border:1px solid #2b364b;border-radius:12px;background:#171e2c;padding:12px}.raw-review-item strong,.raw-review-item small{display:block}.raw-review-item small{color:#98a5bb;margin-top:4px}.raw-review-item button,.raw-review-close{border:1px solid #3c4963;border-radius:9px;background:#202a3d;color:#eef2fa;padding:8px 11px;cursor:pointer}.raw-loading,.raw-error{padding:18px;color:#aab5c8}.raw-error{color:#ffb4bc}
  `;
  document.head.appendChild(style);
  const launch = document.createElement("button");
  launch.className = "raw-review-launch";
  launch.textContent = "Raw-файлы";
  const drawer = document.createElement("aside");
  drawer.className = "raw-review-drawer";
  drawer.innerHTML = '<div class="raw-review-head"><div><h2>Raw-файлы заявок</h2><small>Ссылки действуют 5 минут</small></div><button class="raw-review-close">Закрыть</button></div><div class="raw-review-list"></div>';
  document.body.append(launch, drawer);
  launch.addEventListener("click", () => { drawer.classList.add("open"); void render(drawer.querySelector<HTMLElement>(".raw-review-list")!); });
  drawer.querySelector(".raw-review-close")?.addEventListener("click", () => drawer.classList.remove("open"));
}

window.addEventListener("DOMContentLoaded", mount);
