"""
Отчёты для редакции — агрегация поверх уже существующих таблиц (Order,
OrderItem), без отдельного склада "фактов": для магазина такого размера
считать на лету при каждом открытии отчёта — самый простой вариант, не
плодящий ещё один источник правды, который можно рассинхронизировать с
Order/OrderItem.

Выручка = сумма Order.total (с доставкой, это реальные деньги от клиента)
по заказам, которые были фактически оплачены (payment_status == PAID) и не
отменены впоследствии (status != CANCELLED — см. app/admin.py:OrderAdmin,
отмену можно поставить и после оплаты).

Группировка по дню/месяцу — в Python, а не SQL (func.date_trunc и т.п.),
чтобы отчёт одинаково работал и на Postgres (прод), и на SQLite (локальная
разработка, см. app/database.py) без развилки по диалекту.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Order, OrderItem, OrderStatus, PaymentStatus

ZERO = Decimal("0")


def _paid_orders_query(date_from: datetime, date_to_exclusive: datetime):
    return (
        select(Order)
        .where(Order.payment_status == PaymentStatus.PAID)
        .where(Order.status != OrderStatus.CANCELLED)
        .where(Order.created_at >= date_from)
        .where(Order.created_at < date_to_exclusive)
    )


@dataclass
class RevenueSummary:
    revenue: Decimal
    orders_count: int
    average_check: Decimal


@dataclass
class RevenuePoint:
    label: str
    orders_count: int
    revenue: Decimal


@dataclass
class ProductSales:
    title: str
    quantity: int
    revenue: Decimal


def _paid_orders(db: Session, date_from: datetime, date_to_exclusive: datetime) -> list[Order]:
    return list(db.scalars(_paid_orders_query(date_from, date_to_exclusive)).all())


def revenue_summary(db: Session, date_from: datetime, date_to_exclusive: datetime) -> RevenueSummary:
    orders = _paid_orders(db, date_from, date_to_exclusive)
    revenue = sum((o.total or ZERO for o in orders), ZERO)
    count = len(orders)
    average = (revenue / count) if count else ZERO
    return RevenueSummary(revenue=revenue, orders_count=count, average_check=average)


def revenue_by_period(
    db: Session, date_from: datetime, date_to_exclusive: datetime, group_by: str
) -> list[RevenuePoint]:
    orders = _paid_orders(db, date_from, date_to_exclusive)
    buckets: dict[str, list[Order]] = defaultdict(list)
    fmt = "%Y-%m-%d" if group_by == "day" else "%Y-%m"
    for order in orders:
        buckets[order.created_at.strftime(fmt)].append(order)
    return [
        RevenuePoint(
            label=key,
            orders_count=len(group),
            revenue=sum((o.total or ZERO for o in group), ZERO),
        )
        for key, group in sorted(buckets.items())
    ]


def revenue_by_product(db: Session, date_from: datetime, date_to_exclusive: datetime) -> list[ProductSales]:
    order_ids = [o.id for o in _paid_orders(db, date_from, date_to_exclusive)]
    if not order_ids:
        return []
    items = db.scalars(select(OrderItem).where(OrderItem.order_id.in_(order_ids))).all()
    totals: dict[str, list] = defaultdict(lambda: [0, ZERO])  # title -> [quantity, revenue]
    for item in items:
        agg = totals[item.title]
        agg[0] += item.quantity
        agg[1] += (item.price or ZERO) * item.quantity
    sales = [ProductSales(title=title, quantity=qty, revenue=rev) for title, (qty, rev) in totals.items()]
    sales.sort(key=lambda p: p.revenue, reverse=True)
    return sales
