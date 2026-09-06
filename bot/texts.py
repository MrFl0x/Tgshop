"""Тексты сообщений бота — в одном месте, чтобы не расползались по хендлерам."""

GREETING = (
    "Привет! Это магазин журнала «Чтиво».\n\n"
    "Каталог, оформление заказа и статус доставки — прямо здесь, в Telegram. "
    "Открывайте магазин кнопкой ниже 👇"
)

# Значения ключей — строки OrderStatus.value (app/models.py в backend); бот
# не импортирует backend-модели напрямую (независимые процессы, см.
# docs/TZ-02-bot-i-miniapp.md, ТЗ-1), поэтому список статусов продублирован
# здесь как обычные строки. Статусы Ozon-style — см. tz-zakazy.md и миграцию
# backend 3f0a1c7e2b6d (старые new/paid/assembled/shipped сюда не входят).
STATUS_LABELS = {
    "awaiting_payment": "🆕 ожидает оплаты",
    "awaiting_packaging": "✅ оплачен, собираем",
    "awaiting_deliver": "📦 собран, ждёт отгрузки",
    "delivering": "🚚 в пути",
    "delivered": "📬 доставлен",
    "cancelled": "❌ отменён",
    "returned": "↩️ оформлен возврат",
}


def format_status_notification(
    *,
    order_id: int,
    new_status: str,
    tracking_number: str = "",
    cancel_reason: str = "",
) -> str:
    label = STATUS_LABELS.get(new_status, new_status)
    lines = [f"Заказ №{order_id} — статус изменён: {label}"]
    if tracking_number:
        lines.append(f"Трек-номер: {tracking_number}")
    if new_status == "cancelled" and cancel_reason:
        lines.append(f"Причина отмены: {cancel_reason}")
    return "\n".join(lines)
