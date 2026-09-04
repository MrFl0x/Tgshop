"""
Конфигурация бота — читается из bot/.env (отдельный файл от backend/.env:
процессы независимые, см. docs/TZ-02-bot-i-miniapp.md, ТЗ-1). BOT_TOKEN
должен совпадать со значением в backend/.env — им backend проверяет подпись
initData (app/telegram_auth.py), а бот им же ходит в Bot API.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Mini App (ТЗ-2) — пока не собран, значение по умолчанию — заглушка. Telegram
# открывает web_app-кнопку только на https, поэтому для реальной проверки
# нужен настоящий https-адрес (задеплоенный Mini App или тоннель вроде ngrok).
MINIAPP_URL = os.getenv("MINIAPP_URL", "https://example.com/miniapp")

# Внутренний HTTP-приёмник уведомлений о смене статуса заказа — backend
# стучится сюда (см. app/notifications.py в backend, bot/notify_server.py
# здесь). Секрет должен совпадать с BOT_NOTIFY_SECRET в backend/.env; пустая
# строка отключает проверку (годится только для локальной разработки).
NOTIFY_HOST = os.getenv("BOT_NOTIFY_HOST", "127.0.0.1")
NOTIFY_PORT = int(os.getenv("BOT_NOTIFY_PORT", "8081"))
NOTIFY_SECRET = os.getenv("BOT_NOTIFY_SECRET", "")
