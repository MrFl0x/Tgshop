import { useState } from "react";
import { isInsideTelegram } from "../telegram";

/** Виден только в dev-сборке и только вне настоящего Telegram — позволяет
 * подставить initData вручную (сгенерированную скриптом разработчика с
 * тестовым BOT_TOKEN на backend), чтобы проверять экраны, завязанные на
 * X-Telegram-Init-Data, без реального клиента Telegram. Ничего не подписывает
 * само — секрет бота во фронтенд не попадает. См. README «Разработка вне
 * Telegram». В production-сборке этот компонент не рендерится (import.meta.env.DEV
 * статически false — Vite вырезает мёртвый код при сборке). */
export function DevBanner() {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(() => localStorage.getItem("dev_init_data") ?? "");

  if (!import.meta.env.DEV || isInsideTelegram()) return null;

  return (
    <div className="dev-banner">
      DEV: приложение открыто не в Telegram — initData пуст, запросы с
      авторизацией вернут 401.{" "}
      <button
        className="copy-btn"
        style={{ marginLeft: 6 }}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "Скрыть" : "Задать initData"}
      </button>
      {open && (
        <div style={{ marginTop: 8, textAlign: "left" }}>
          <textarea
            style={{ width: "100%", minHeight: 60, fontFamily: "monospace", fontSize: 11 }}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="query_id=...&user=...&auth_date=...&hash=..."
          />
          <button
            className="btn btn-secondary btn-sm"
            style={{ marginTop: 6 }}
            onClick={() => {
              localStorage.setItem("dev_init_data", value);
              location.reload();
            }}
          >
            Сохранить и перезагрузить
          </button>
        </div>
      )}
    </div>
  );
}
