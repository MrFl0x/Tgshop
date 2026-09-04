"""Тексты сообщений бота — в одном месте, чтобы не расползались по хендлерам."""

GREETING = (
    "Привет! Это магазин журнала «Чтиво».\n\n"
    "Каталог, оформление заказа и статус доставки — прямо здесь, в Telegram. "
    "Открывайте магазин кнопкой ниже 👇"
)

# Значения ключей — строки OrderStatus (app/models.py в backend); бот не
# импортирует backend-модели напрямую (независимые процессы, см.
# docs/TZ-02-bot-i-miniapp.md, ТЗ-1), поэтому список статусов продублирован
# здесь как обычные строки.
STATUS_LABELS = {
    "new": "🆕 новый",
    "paid": "✅ оплачен",
    "assembled": "📦 собран",
    "shipped": "🚚 в пути",
    "delivered": "📬 доставлен",
    "cancelled": "❌ отменён",
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
