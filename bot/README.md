# Чтиво · Магазин — бот (aiogram 3)

Отдельный процесс от backend (`../backend`) — не импортирует `app.models`,
общаются они только через HTTP: backend best-effort стучится в маленький
внутренний приёмник этого бота при смене статуса заказа. См.
[docs/TZ-02-bot-i-miniapp.md](../docs/TZ-02-bot-i-miniapp.md), ТЗ-1 и ТЗ-3 п.1.

## Что уже есть

- **`/start`** — приветствие и кнопка «Открыть магазин» (`WebAppInfo`,
  [keyboards.py](keyboards.py)).
- **Реферальный deep-link** — `/start CHT00001` (ссылка вида
  `t.me/<bot>?start=CHT00001`, код — `Customer.referral_code` из backend).
  Код запоминается в памяти процесса ([referrals.py](referrals.py)) и
  прокидывается в URL Mini App параметром `startapp` при построении
  клавиатуры — дальше Mini App должна передать его как `referral_code` в
  `POST /orders/`. Повторный `/start` без кода погашенный код не трогает.
- **Уведомления о смене статуса заказа** — [notify_server.py](notify_server.py)
  поднимает свой маленький HTTP-приёмник (`POST /internal/order-status`,
  порт из `BOT_NOTIFY_PORT`), backend дёргает его из
  `app/order_history.py:record_order_status_change`
  (см. `backend/app/notifications.py`). Бот пересылает сообщение клиенту тем
  же `Bot`, что держит long polling.

## Запуск (Windows / PowerShell)

Из корня репозитория — важно: бот запускается модулем (`-m bot.main`), а не
файлом напрямую, иначе относительные импорты (`from .config import ...`) не
сработают.

```powershell
py -3 -m venv .venv-bot
.\.venv-bot\Scripts\python.exe -m pip install -r bot\requirements.txt
Copy-Item bot\.env.example bot\.env   # один раз — заполнить BOT_TOKEN
.\.venv-bot\Scripts\python.exe -m bot.main
```

- `BOT_TOKEN` — токен от [@BotFather](https://t.me/BotFather), тот же, что в
  `backend/.env` (backend им проверяет подпись `initData`, см.
  `app/telegram_auth.py`).
- `MINIAPP_URL` — адрес Mini App (ТЗ-2, ещё не собран). Telegram открывает
  `web_app`-кнопку только на `https` — для локальной проверки самого бота
  можно оставить заглушку из `.env.example`, кнопка появится в чате, но не
  откроется, пока здесь не будет настоящий https-адрес.
- Для уведомлений backend и бот должны работать одновременно; если бот не
  запущен, backend просто логирует предупреждение и не роняет смену статуса
  заказа (см. `backend/app/notifications.py`).

## Чего пока нет

- `/orders` — последние заказы клиента текстом (опционально по ТЗ-1).
  `GET /customers/{telegram_id}/orders` в backend уже есть (ТЗ-3 п.2,
  `backend/app/routers/customers.py`) — саму команду в боте ещё не завели.
- Экран «Профиль» с реферальной ссылкой клиента и бонусным балансом — это
  часть Mini App (ТЗ-2), не бота.
- Webhook вместо long polling — отдельная задача при деплое на реальный
  сервер (см. ТЗ-1).
