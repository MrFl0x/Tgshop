/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_BOT_USERNAME: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Минимальные типы для window.Telegram.WebApp — покрывают только то, что
// реально используется в приложении (см. src/telegram.ts). Полный контракт —
// https://core.telegram.org/bots/webapps#initializing-mini-apps
interface TelegramWebAppThemeParams {
  bg_color?: string;
  text_color?: string;
  hint_color?: string;
  link_color?: string;
  button_color?: string;
  button_text_color?: string;
  secondary_bg_color?: string;
  destructive_text_color?: string;
}

interface TelegramWebAppUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
}

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: { user?: TelegramWebAppUser; start_param?: string };
  themeParams: TelegramWebAppThemeParams;
  colorScheme: "light" | "dark";
  viewportStableHeight: number;
  ready(): void;
  expand(): void;
  close(): void;
  onEvent(event: string, handler: () => void): void;
  offEvent(event: string, handler: () => void): void;
  BackButton: {
    show(): void;
    hide(): void;
    onClick(handler: () => void): void;
    offClick(handler: () => void): void;
  };
  MainButton: {
    text: string;
    color: string;
    textColor: string;
    isVisible: boolean;
    isActive: boolean;
    show(): void;
    hide(): void;
    enable(): void;
    disable(): void;
    setText(text: string): void;
    onClick(handler: () => void): void;
    offClick(handler: () => void): void;
  };
  HapticFeedback?: {
    impactOccurred(style: "light" | "medium" | "heavy" | "rigid" | "soft"): void;
    notificationOccurred(type: "error" | "success" | "warning"): void;
  };
}

interface Window {
  Telegram?: { WebApp?: TelegramWebApp };
}
