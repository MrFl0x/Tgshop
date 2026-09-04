"""
Внутренний HTTP-приёмник уведомлений о смене статуса заказа. backend дёргает
его напрямую при каждой записи в OrderStatusHistory (см. в backend
app/notifications.py → app/order_history.py), бот пересылает сообщение
клиенту тем же Bot-инстансом, что держит long polling.

Выбран этот вариант интеграции (push из backend), а не альтернативный
(бот сам поллит `/orders/{id}/history`) — см. docs/TZ-02-bot-i-miniapp.md,
ТЗ-3 п.1, где явно сказано выбрать один вариант, не оба.
"""
import logging

from aiogram import Bot
from aiohttp import web

from .config import NOTIFY_SECRET
from .texts import format_status_notification

logger = logging.getLogger(__name__)


def build_notify_app(bot: Bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/internal/order-status", _handle_order_status)
    return app


async def _handle_order_status(request: web.Request) -> web.Response:
    if NOTIFY_SECRET and request.headers.get("X-Notify-Secret") != NOTIFY_SECRET:
        return web.json_response({"detail": "bad secret"}, status=401)

    try:
        payload = await request.json()
    except ValueError:
        return web.json_response({"detail": "bad json"}, status=400)

    telegram_id = payload.get("telegram_id")
    order_id = payload.get("order_id")
    new_status = payload.get("new_status")
    if not telegram_id or not order_id or not new_status:
        return web.json_response({"detail": "telegram_id, order_id и new_status обязательны"}, status=400)

    try:
        chat_id = int(telegram_id)
    except (TypeError, ValueError):
        logger.warning("Некорректный telegram_id в уведомлении о заказе №%s: %r", order_id, telegram_id)
        return web.json_response({"detail": "bad telegram_id"}, status=400)

    text = format_status_notification(
        order_id=order_id,
        new_status=new_status,
        tracking_number=payload.get("tracking_number") or "",
        cancel_reason=payload.get("cancel_reason") or "",
    )

    bot: Bot = request.app["bot"]
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except Exception:
        # Клиент мог заблокировать бота/удалить чат — не ошибка запроса,
        # backend и так шлёт уведомление best-effort (см. там же
        # app/notifications.py) и не должен падать из-за недоставки.
        logger.warning(
            "Не удалось отправить уведомление клиенту %s о заказе №%s", chat_id, order_id, exc_info=True
        )
        return web.json_response({"delivered": False}, status=200)

    return web.json_response({"delivered": True})
