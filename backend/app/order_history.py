"""
Запись переходов Order.status в OrderStatusHistory — общая точка для
routers/orders.py (автопереход при оплате) и app/admin.py (правка статуса
редактором вручную), чтобы формат записи не разъезжался между двумя местами.
Здесь же — единственная точка, где дёргается уведомление клиента в Telegram
(app/notifications.py), чтобы оно не забывалось при появлении третьего места
смены статуса (см. docs/TZ-02-bot-i-miniapp.md, ТЗ-3 п.1).
"""
from sqlalchemy.orm import Session

from .models import Order, OrderStatus, OrderStatusHistory
from .notifications import notify_order_status_change


def record_order_status_change(
    db: Session,
    order: Order,
    old_status: OrderStatus,
    new_status: OrderStatus,
    *,
    changed_by: str = "system",
    note: str = "",
) -> None:
    """Не пишет запись, если статус фактически не изменился (например,
    оплата упала и заказ остался в NEW)."""
    if old_status == new_status:
        return
    db.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=old_status,
            to_status=new_status,
            changed_by=changed_by,
            note=note,
        )
    )
    notify_order_status_change(order, old_status, new_status)
