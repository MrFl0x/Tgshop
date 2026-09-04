# Чтиво · Магазин — Mini App (React + TypeScript)

Витрина поверх готового backend (`../backend`) — React + Telegram WebApp SDK
(`window.Telegram.WebApp`, скрипт из `index.html`), без `@telegram-apps/sdk`
как отдельной зависимости: того, что даёт сырой `window.Telegram.WebApp`,
достаточно для набора экранов этого этапа (initData, тема, кнопки). См.
[docs/TZ-02-bot-i-miniapp.md](../docs/TZ-02-bot-i-miniapp.md), ТЗ-2.

## Экраны (ТЗ-2, все реализованы)

1. **Каталог** (`/`) — `GET /products/`.
2. **Карточка товара** (`/product/:id`) — `GET /products/{id}`, выбор
   количества, «в корзину».
3. **Корзина** (`/cart`) — локальное состояние в `localStorage`
   (`src/state/CartContext.tsx`), не хранится на backend, пока заказ не
   оформлен.
4. **Оформление** (`/checkout`) — способ доставки (`GET /delivery-methods/`),
   адрес (сохранённый из адресной книги или новый, опция сохранить),
   `POST /orders/`, затем сразу `POST /orders/{id}/pay` (заглушка — см.
   `backend/app/payments.py`).
5. **Статус заказа** (`/orders/:id`) — `GET /orders/{id}` +
   `GET /orders/{id}/history`, таймлайн переходов статуса.
6. **Профиль** (`/profile`) — бонусный баланс и реферальная ссылка
   (`t.me/<бот>?start=<referral_code>`), `GET /customers/{telegram_id}`.
7. **Мои заказы** (`/orders`) — `GET /customers/{telegram_id}/orders`.

Роутинг — `HashRouter` (react-router-dom): URL вида `/#/cart`. Осознанный
выбор для этого этапа — работает на любом статическом хостинге без настройки
сервера под SPA-фолбэк (хостинг Mini App ещё не выбран, см. открытые вопросы
продуктового брифа). Если/когда появится сервер с контролем над роутингом —
переход на `BrowserRouter` это одна строка в `src/App.tsx`.

## Как backend узнаёт, кто спрашивает

Telegram кладёt в Mini App подписанную строку `initData`
(`window.Telegram.WebApp.initData`). Каждый запрос к backend, которому нужен
`telegram_id` (всё, кроме каталога и списка способов доставки), несёт её в
заголовке `X-Telegram-Init-Data` — см. `src/api/client.ts`. Backend проверяет
подпись сам (`app/telegram_auth.py`, ТЗ-0) — фронтенд ничего не подписывает и
секрет бота не хранит.

## Запуск

```powershell
cd miniapp
npm install
Copy-Item .env.example .env    # один раз — VITE_API_BASE_URL, VITE_BOT_USERNAME
npm run dev
```

Backend (`../backend`) должен быть запущен отдельно — см. `backend/README.md`.
CORS на его стороне разрешает `http://localhost:5173` по умолчанию
(`CORS_ORIGINS` в `backend/.env`, см. `app/main.py`).

## Разработка вне Telegram

Открыть `http://localhost:5173` напрямую в браузере тоже можно — каталог и
карточка товара работают (это публичные эндпоинты), но `initData` там пустой,
и всё, что требует `X-Telegram-Init-Data` (корзина → заказ, «Мои заказы»,
«Профиль»), получит 401 — так и должно быть, backend не может отличить
браузер от подделки без подписи.

Для проверки этих экранов без реального клиента Telegram — на странице
появляется dev-баннер (`src/components/DevBanner.tsx`, виден только в
`npm run dev`, вырезается из production-сборки) с полем для вставки готовой
строки `initData`. Такую строку нужно сгенерировать отдельно (подписав тем же
алгоритмом, что и `app/telegram_auth.py:verify_init_data`, тестовым
`BOT_TOKEN`, которым в этот момент временно запущен backend) — фронтенд сам
ничего не подписывает, это чисто ручной шаг для локальной отладки.

Полноценная проверка — всегда через настоящий Telegram: `MINIAPP_URL` в
`bot/.env` должен указывать на реально доступный `https`-адрес (Telegram не
откроет `web_app`-кнопку на `http`); для локальной разработки подойдёт
туннель (ngrok и т.п.).

## Чего пока нет

- Фирменные обложки номеров — `Product.cover_url` пуст у тестовых товаров
  (`backend/app/seed.py`), карточка показывает заглушку с названием.
- Настоящая форма оплаты ЮKassa — после `POST /orders/{id}/pay`-заглушки
  сразу открывается статус заказа; когда подключится ЮKassa (этап 04), здесь
  появится редирект на форму оплаты — вызов с фронтенда не изменится.
- Реальный расчёт стоимости `calculated`-способов доставки — показывает то
  же фиксированное число, что отдаёт backend (`fixed_cost`, заглушка).
- Деплой — куда и как хостить статическую сборку (`npm run build` → `dist/`),
  не решено; см. открытые вопросы продуктового брифа.
