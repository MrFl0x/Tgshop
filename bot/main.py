"""
Точка входа бота — отдельный процесс от backend (см.
docs/TZ-02-bot-i-miniapp.md, ТЗ-1): не импортирует app.models, общается с
backend только тем, что backend сам стучится в наш внутренний приёмник
уведомлений (notify_server.py). Так бот и API можно рестартовать/деплоить
по отдельности.

Запуск из корня репозитория (после `pip install -r bot/requirements.txt` и
заполнения bot/.env — см. bot/.env.example):

    python -m bot.main
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

from .config import BOT_TOKEN, NOTIFY_HOST, NOTIFY_PORT
from .handlers.start import router as start_router
from .notify_server import build_notify_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN не задан — заполните bot/.env (см. bot/.env.example)")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(start_router)

    runner = web.AppRunner(build_notify_app(bot))
    await runner.setup()
    site = web.TCPSite(runner, NOTIFY_HOST, NOTIFY_PORT)
    await site.start()
    logger.info("Внутренний приёмник уведомлений слушает http://%s:%s", NOTIFY_HOST, NOTIFY_PORT)

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
