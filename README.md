# 📚 Чтиво · Магазин

Telegram-магазин литературного медиа «Чтиво»: бот + Mini App + backend.
Каталог (номера, подписки, мерч), доставка, оплата, бонусы и рефералка —
без сайта, целиком внутри Telegram.

[![Backend](https://img.shields.io/badge/backend-FastAPI-009688)](backend)
[![Bot](https://img.shields.io/badge/bot-aiogram%203-2CA5E0)](bot)
[![Mini App](https://img.shields.io/badge/miniapp-React%20%2B%20TS-61DAFB)](miniapp)
[![DB](https://img.shields.io/badge/db-PostgreSQL-336791)](backend)

---

## Что это

Читатель нажимает `/start` у бота → открывает Mini App как витрину →
выбирает товар, способ доставки, оформляет заказ → бот присылает
уведомления о смене статуса. Админка (веб, без кода) — для редакции:
товары, доставка, заказы, редакторы.

```
Telegram-клиент
   │
   ├── Bot (aiogram)        — /start, deep-link рефералки, уведомления
   └── Mini App (React)     — каталог, корзина, оформление, профиль
           │
           ▼
      Backend (FastAPI) ── PostgreSQL
           │
           └── SQLAdmin — веб-панель редакции (/admin)
```

Три процесса разворачиваются и деплоятся независимо; общаются только по HTTP
(Mini App и бот не импортируют код backend напрямую).

## Модули

| Модуль | Стек | Что делает | Подробнее |
|---|---|---|---|
| [`backend/`](backend) | FastAPI, PostgreSQL, Alembic, SQLAdmin | Каталог, заказы, доставка, клиенты, бонусы, склад, оплата | [backend/README.md](backend/README.md) |
| [`bot/`](bot) | aiogram 3 | Точка входа, deep-link рефералки, уведомления о статусе заказа | [bot/README.md](bot/README.md) |
| [`miniapp/`](miniapp) | React + TypeScript | Витрина: каталог → корзина → оформление → статус заказа | [miniapp/README.md](miniapp/README.md) |

## Возможности (MVP)

- 🛍️ Каталог товаров (номера журнала, подписки, мерч) с остатками
- 🚚 Доставка: самовывоз, СДЭК, Boxberry, Почта России, свой курьер
- 📦 Заказы со статус-историей (кто и когда менял) и уведомлениями в бот
- 👤 Профиль, адресная книга, «Мои заказы»
- 🎁 Реферальная программа и бонусный баланс
- 🔐 Проверка подлинности запросов по подписи Telegram `initData`
- 🛠️ Веб-админка для редакции без правки кода

Статус каждого пункта и то, чего ещё нет — в README модуля.

## Быстрый старт

Поднять всё для локальной разработки — по порядку, в трёх терминалах:

```powershell
# 1. backend
cd backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# 2. bot
py -3 -m venv .venv-bot
.\.venv-bot\Scripts\python.exe -m pip install -r bot\requirements.txt
Copy-Item bot\.env.example bot\.env   # заполнить BOT_TOKEN
.\.venv-bot\Scripts\python.exe -m bot.main

# 3. miniapp
cd miniapp
npm install
Copy-Item .env.example .env
npm run dev
```

Детали (переменные окружения, туннель для Mini App, смена БД на Supabase/
Selectel) — в README каждого модуля.

## Документация

- [docs/TZ-02-bot-i-miniapp.md](docs/TZ-02-bot-i-miniapp.md) — ТЗ на бота и Mini App
- [docs/TZ-03-zakryt-dyru-i-miniapp.md](docs/TZ-03-zakryt-dyru-i-miniapp.md) — ТЗ на закрытие уязвимости доступа к чужим заказам

## Дальше по плану

- Реальный расчёт стоимости доставки (СДЭК/Boxberry API)
- Оплата ЮKassa вместо заглушки
- Автопродление подписок
- Перенос базы данных на российский хостинг (152-ФЗ) перед первым реальным клиентом

Подробный трекинг — в разделах «Дальше по плану» / «Чего пока нет» README модулей.
