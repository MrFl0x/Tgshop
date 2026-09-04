"""
Уведомление клиента в Telegram при смене статуса заказа. Backend не говорит с
Bot API сам — он best-effort стучится в маленький внутренний HTTP-приёмник
бота (bot/notify_server.py), а бот уже сам решает, что и как написать в чат.
Выбранный вариант интеграции — прямой HTTP-вызов из backend, а не поллинг
ботом `/orders/{id}/history` — см. docs/TZ-02-bot-i-miniapp.md, ТЗ-3 п.1
(там явно сказано выбрать один вариант, не оба).
"""
import json
import logging
import os
import urllib.error
import urllib.request

from .models import Order, OrderStatus

logger = logging.getLogger(__name__)

BOT_NOTIFY_URL = os.getenv("BOT_NOTIFY_URL", "http://127.0.0.1:8081/internal/order-status")
BOT_NOTIFY_SECRET = os.getenv("BOT_NOTIFY_SECRET", "")
NOTIFY_TIMEOUT_SECONDS = 3


def notify_order_status_change(order: Order, old_status: OrderStatus | None, new_status: OrderStatus) -> None:
    """Best-effort: бот может быть временно выключен/недоступен — это не
    должно ронять смену статуса заказа в БД (вызывается из
    order_history.record_order_status_change до коммита вызывающей стороны)."""
    customer = order.customer
    if not customer or not customer.telegram_id:
        return  # гостевой заказ либо клиент ещё не привязан к Telegram

    payload = {
        "telegram_id": customer.telegram_id,
        "order_id": order.id,
        "old_status": old_status.value if old_status else None,
        "new_status": new_status.value,
        "tracking_number": order.tracking_number or "",
        "cancel_reason": order.cancel_reason or "",
    }
    request = urllib.request.Request(
        BOT_NOTIFY_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Notify-Secret": BOT_NOTIFY_SECRET,
        },
    )
    try:
        urllib.request.urlopen(request, timeout=NOTIFY_TIMEOUT_SECONDS)
    except (urllib.error.URLError, OSError):
        # Обычное дело в разработке, если бот сейчас не запущен — не должно
        # мешать сохранению статуса. TODO: если пропуски уведомлений станут
        # проблемой на реальном объёме — очередь с ретраями вместо
        # fire-and-forget (см. этап 05 дорожной карты).
        logger.warning("Не удалось отправить уведомление о заказе №%s боту", order.id, exc_info=True)
