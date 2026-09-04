// Тонкая обёртка над window.Telegram.WebApp (см. src/vite-env.d.ts).
// Используем сырой window.Telegram.WebApp, а не @telegram-apps/sdk — для
// того набора возможностей, что нужен здесь (initData, тема, кнопки), это
// не даёт заметного выигрыша, а лишней зависимости меньше.

function getWebApp(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null;
}

/** true, если приложение реально открыто внутри Telegram (а не в обычном
 * браузере при разработке) — по наличию непустого initData. */
export function isInsideTelegram(): boolean {
  return !!getWebApp()?.initData;
}

/** Сырая подписанная строка initData — кладётся в заголовок
 * X-Telegram-Init-Data на каждый запрос к backend (см. api/client.ts).
 * В dev-режиме вне Telegram — резерв из localStorage, см. README раздел
 * «Разработка вне Telegram». */
export function getInitData(): string {
  const real = getWebApp()?.initData;
  if (real) return real;
  if (import.meta.env.DEV) {
    return localStorage.getItem("dev_init_data") ?? "";
  }
  return "";
}

/** telegram_id текущего пользователя — разобран из той же initData, что
 * уходит в заголовок (см. getInitData), а не из initDataUnsafe напрямую:
 * так работает одинаково и в реальном Telegram, и с dev-заглушкой из
 * localStorage (initDataUnsafe её не видит, это чисто SDK-объект). Backend
 * всё равно перепроверяет подпись сам — это только для адресации
 * GET /customers/{telegram_id}/... на фронте. */
export function getCurrentUserId(): string | null {
  const raw = getInitData();
  if (!raw) return null;
  try {
    const params = new URLSearchParams(raw);
    const userRaw = params.get("user");
    if (!userRaw) return null;
    const user = JSON.parse(userRaw) as { id?: number };
    return user.id != null ? String(user.id) : null;
  } catch {
    return null;
  }
}

export function getStartParam(): string | undefined {
  return getWebApp()?.initDataUnsafe.start_param;
}

export function initTelegramWebApp(): void {
  const app = getWebApp();
  if (!app) return;
  app.ready();
  app.expand();
  applyThemeVars(app.themeParams);
  app.onEvent("themeChanged", () => applyThemeVars(app.themeParams));
}

/** Прокидывает themeParams Telegram поверх фирменной палитры «Чтиво»
 * (см. src/styles/theme.css) — заказчик Mini App может быть в тёмной теме
 * клиента Telegram, наш бренд подстраивается под неё, а не игнорирует. */
function applyThemeVars(theme: TelegramWebAppThemeParams): void {
  const root = document.documentElement.style;
  if (theme.bg_color) root.setProperty("--tg-bg", theme.bg_color);
  if (theme.text_color) root.setProperty("--tg-text", theme.text_color);
  if (theme.hint_color) root.setProperty("--tg-hint", theme.hint_color);
  if (theme.button_color) root.setProperty("--tg-button", theme.button_color);
  if (theme.button_text_color) root.setProperty("--tg-button-text", theme.button_text_color);
  if (theme.secondary_bg_color) root.setProperty("--tg-bg-2", theme.secondary_bg_color);
}

export function hapticSuccess(): void {
  getWebApp()?.HapticFeedback?.notificationOccurred("success");
}

export function hapticError(): void {
  getWebApp()?.HapticFeedback?.notificationOccurred("error");
}

export function hapticTap(): void {
  getWebApp()?.HapticFeedback?.impactOccurred("light");
}

export { getWebApp };
