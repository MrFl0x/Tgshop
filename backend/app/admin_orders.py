"""
Раздел «Заказы» панели редакции — написанный вручную BaseView (по образцу
RevenueReportView в app/admin.py), а не ModelView поверх Order: вид по ТЗ
(вкладки по статусу, дашборд-карточки, карточка заказа из 5 блоков, массовые
действия, экспорт, PDF-этикетки) сильно расходится с тем, что sqladmin рисует
для модели по умолчанию — проще и надёжнее держать свою вёрстку в
templates/orders/, чем подгонять под неё чужую. Ориентир — личный кабинет
продавца Ozon.

Три места пишут Order.status: pay_order (routers/orders.py — единственный
переход, который происходит автоматически по оплате, без кнопки) и три
действия здесь (advance_status/cancel_order_route/create_return_route). Все —
через order_history.record_order_status_change, чтобы уведомление клиенту в
бот не забылось при появлении места смены статуса (см. этот же принцип в
самом order_history.py).
"""
from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from openpyxl import Workbook
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqladmin import BaseView, Flash, expose
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response, StreamingResponse

from .database import SessionLocal
from .models import (
    DeliveryMethod,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    PaymentStatus,
    PaymentTransaction,
    Product,
    Return,
    ReturnStatus,
    StockMovement,
    StockMovementReason,
)
from .order_history import record_order_status_change

PER_PAGE = 30

STATUS_LABELS_RU = {
    OrderStatus.AWAITING_PAYMENT: "Ожидает оплаты",
    OrderStatus.AWAITING_PACKAGING: "Ожидает сборки",
    OrderStatus.AWAITING_DELIVER: "Ожидает отгрузки",
    OrderStatus.DELIVERING: "Доставляется",
    OrderStatus.DELIVERED: "Доставлен",
    OrderStatus.CANCELLED: "Отменён",
    OrderStatus.RETURNED: "Возврат",
}
# Цвета бейджей — как в ТЗ: ожидание серое, требует действия — оранжевое,
# в пути — синее, доставлен — зелёный, отменён/возврат — красный.
STATUS_BADGE_CLASS = {
    OrderStatus.AWAITING_PAYMENT: "bg-secondary",
    OrderStatus.AWAITING_PACKAGING: "bg-orange",
    OrderStatus.AWAITING_DELIVER: "bg-orange",
    OrderStatus.DELIVERING: "bg-blue",
    OrderStatus.DELIVERED: "bg-success",
    OrderStatus.CANCELLED: "bg-danger",
    OrderStatus.RETURNED: "bg-danger",
}
PAYMENT_STATUS_LABELS_RU = {
    PaymentStatus.PENDING: "Ожидает",
    PaymentStatus.PAID: "Оплачен",
    PaymentStatus.FAILED: "Не прошла",
    PaymentStatus.REFUNDED: "Возвращена",
}
RETURN_STATUS_LABELS_RU = {
    ReturnStatus.REQUESTED: "Запрошен",
    ReturnStatus.APPROVED: "Одобрен",
    ReturnStatus.REJECTED: "Отклонён",
    ReturnStatus.COMPLETED: "Завершён",
}
# Линейный ход выполнения для вкладок и кнопки «следующий шаг». Специально
# без AWAITING_PAYMENT: переход из него — только автоматически по оплате
# (routers/orders.py:pay_order), кнопки на это в карточке нет (см. ТЗ, п.4:
# "автоматически по вебхуку от платёжного провайдера").
STATUS_FLOW = [
    OrderStatus.AWAITING_PACKAGING,
    OrderStatus.AWAITING_DELIVER,
    OrderStatus.DELIVERING,
    OrderStatus.DELIVERED,
]
NEXT_STATUS_LABEL = {
    # Ключ — тот статус, В КОТОРЫЙ ведёт кнопка (next_status в order_detail
    # ниже), а не текущий: тройка ниже — это STATUS_FLOW[1:], три реально
    # достижимых next_status. Раньше словарь был сдвинут на шаг (ключом стоял
    # AWAITING_PACKAGING, в который перейти кнопкой нельзя — это первый статус
    # потока) — из-за этого на DELIVERING кнопка рендерила буквально "None →"
    # (next_status_label не находился, detail.html подставлял None как есть).
    OrderStatus.AWAITING_DELIVER: "Собран",
    OrderStatus.DELIVERING: "Передан курьеру",
    OrderStatus.DELIVERED: "Вручён",
}
TABS = [
    ("Все", None),
    ("Ожидают оплаты", OrderStatus.AWAITING_PAYMENT),
    ("Ожидают сборки", OrderStatus.AWAITING_PACKAGING),
    ("Ожидают отгрузки", OrderStatus.AWAITING_DELIVER),
    ("Доставляются", OrderStatus.DELIVERING),
    ("Доставлены", OrderStatus.DELIVERED),
    ("Отменены", OrderStatus.CANCELLED),
    ("Возвраты", OrderStatus.RETURNED),
]
# Отмена возможна из любого статуса до DELIVERING (см. ТЗ, п.4).
CAN_CANCEL_STATUSES = {OrderStatus.AWAITING_PAYMENT, OrderStatus.AWAITING_PACKAGING, OrderStatus.AWAITING_DELIVER}


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def _apply_filters(query, params) -> object:
    """params — что угодно с `.get(name)` (Starlette QueryParams или обычный
    dict): список заказов, счётчики вкладок и оба экспорта используют один и
    тот же набор фильтров, чтобы они не могли разойтись."""
    status = params.get("status")
    if status and status != "all":
        try:
            query = query.filter(Order.status == OrderStatus(status))
        except ValueError:
            pass

    search = (params.get("search") or "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Order.number.ilike(like),
                Order.customer_name.ilike(like),
                Order.customer_contact.ilike(like),
                Order.tracking_number.ilike(like),
            )
        )

    date_from = _parse_date(params.get("date_from"))
    if date_from:
        query = query.filter(Order.created_at >= date_from)
    date_to = _parse_date(params.get("date_to"))
    if date_to:
        query = query.filter(Order.created_at < date_to + timedelta(days=1))

    payment_method = params.get("payment_method")
    if payment_method:
        query = query.filter(Order.payment_method == payment_method)

    delivery_method_id = params.get("delivery_method_id")
    if delivery_method_id:
        try:
            query = query.filter(Order.delivery_method_id == int(delivery_method_id))
        except ValueError:
            pass

    product_id = params.get("product_id")
    if product_id:
        try:
            query = query.filter(Order.items.any(OrderItem.product_id == int(product_id)))
        except ValueError:
            pass

    return query


def _plural_ru(n: int, one: str, few: str, many: str) -> str:
    """Склонение числительного (заказ/заказа/заказов и т.п.) — стандартные
    правила русского языка (последние 1-2 цифры числа решают форму)."""
    n_abs = abs(n) % 100
    if 11 <= n_abs <= 14:
        return many
    last_digit = n_abs % 10
    if last_digit == 1:
        return one
    if 2 <= last_digit <= 4:
        return few
    return many


def _is_pickup(order: Order) -> bool:
    return bool(order.delivery_method and not order.delivery_method.requires_address)


def _changed_by(request: Request) -> str:
    return request.session.get("admin_username") or "admin"


class OrdersPanelView(BaseView):
    """`list_orders` намеренно объявлен первым методом в классе: sqladmin
    определяет, на какой URL ведёт пункт меню, по ПОСЛЕДНЕМУ обработанному
    при регистрации `@expose`-методу, а обрабатывает их в порядке, обратном
    объявлению в исходнике (см. sqladmin/application.py:_find_decorated_funcs)
    — то есть верхний метод в файле регистрируется последним и "выигрывает"
    ссылку в левом меню. Остальные методы ниже адресуются напрямую через
    `url_for("admin:view-<identity>", ...)` с их собственным identity — это не
    зависит от порядка."""

    name = "Заказы"
    name_plural = "Заказы"
    identity = "orders_list"
    icon = "fa-solid fa-receipt"

    @expose("/orders", methods=["GET"], identity="orders_list")
    async def list_orders(self, request: Request) -> Response:
        db = SessionLocal()
        try:
            base = db.query(Order).options(
                joinedload(Order.customer), joinedload(Order.items).joinedload(OrderItem.product)
            )
            filtered = _apply_filters(base, request.query_params)

            sort = request.query_params.get("sort") or "-created_at"
            column = Order.total if sort.lstrip("-") == "total" else Order.created_at
            filtered = filtered.order_by(column.desc() if sort.startswith("-") else column.asc())

            page = max(1, int(request.query_params.get("page") or 1))
            total_count = filtered.count()
            total_pages = max(1, (total_count + PER_PAGE - 1) // PER_PAGE)
            orders = filtered.offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()
            # order_by(None) — filtered уже несёт ORDER BY orders.created_at/total
            # (см. выше), а with_entities() меняет список колонок SELECT, не
            # трогая ORDER BY: без сброса Postgres требует created_at в GROUP BY.
            total_sum = filtered.order_by(None).with_entities(func.coalesce(func.sum(Order.total), 0)).scalar() or 0

            # Счётчики вкладок — с теми же фильтрами, кроме самого статуса
            # (как в Ozon: если что-то искали, вкладки считают только это).
            other_params = {k: v for k, v in request.query_params.items() if k != "status"}
            counts_query = _apply_filters(
                db.query(Order.status, func.count(Order.id)).group_by(Order.status), other_params
            )
            counts_by_status = dict(counts_query.all())
            tab_counts = {"all": sum(counts_by_status.values())}
            for status_enum, count in counts_by_status.items():
                tab_counts[status_enum.value] = count

            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            orders_today = db.query(func.count(Order.id)).filter(Order.created_at >= today_start).scalar() or 0

            period_start = datetime.utcnow() - timedelta(days=30)
            paid_recent = db.query(Order).filter(
                Order.created_at >= period_start, Order.payment_status == PaymentStatus.PAID
            )
            revenue_30d = paid_recent.with_entities(func.coalesce(func.sum(Order.total), 0)).scalar() or 0
            paid_count_30d = paid_recent.count()
            average_check = (revenue_30d / paid_count_30d) if paid_count_30d else 0

            context = {
                "request": request,
                "orders": orders,
                "page": page,
                "total_pages": total_pages,
                "total_count": total_count,
                "total_sum": total_sum,
                "orders_word": _plural_ru(total_count, "заказ", "заказа", "заказов"),
                "tabs": TABS,
                "tab_counts": tab_counts,
                "current_status": request.query_params.get("status") or "all",
                "search": request.query_params.get("search", ""),
                "date_from": request.query_params.get("date_from", ""),
                "date_to": request.query_params.get("date_to", ""),
                "payment_method": request.query_params.get("payment_method", ""),
                "delivery_method_id": request.query_params.get("delivery_method_id", ""),
                "sort": sort,
                "delivery_methods": db.query(DeliveryMethod).order_by(DeliveryMethod.sort_order).all(),
                "status_labels": STATUS_LABELS_RU,
                "status_badge_class": STATUS_BADGE_CLASS,
                "stats": {
                    "orders_today": orders_today,
                    "revenue_30d": revenue_30d,
                    "average_check": average_check,
                    "awaiting_packaging": counts_by_status.get(OrderStatus.AWAITING_PACKAGING, 0),
                },
            }
            return await self.templates.TemplateResponse(request, "orders/list.html", context)
        finally:
            db.close()

    @expose("/orders/{order_id}", methods=["GET"], identity="orders_detail")
    async def order_detail(self, request: Request) -> Response:
        order_id = int(request.path_params["order_id"])
        db = SessionLocal()
        try:
            order = (
                db.query(Order)
                .options(
                    joinedload(Order.customer),
                    joinedload(Order.delivery_method),
                    joinedload(Order.address),
                    joinedload(Order.items).joinedload(OrderItem.product),
                    joinedload(Order.returns),
                )
                .filter(Order.id == order_id)
                .first()
            )
            if not order:
                raise HTTPException(status_code=404, detail="Заказ не найден")

            history = (
                db.query(OrderStatusHistory)
                .filter_by(order_id=order.id)
                .order_by(OrderStatusHistory.id.desc())
                .all()
            )
            payments = (
                db.query(PaymentTransaction).filter_by(order_id=order.id).order_by(PaymentTransaction.id.desc()).all()
            )
            past_orders_count = 0
            if order.customer_id:
                past_orders_count = (
                    db.query(func.count(Order.id))
                    .filter(Order.customer_id == order.customer_id, Order.id != order.id)
                    .scalar()
                    or 0
                )

            next_status = None
            can_advance = False
            advance_block_reason = ""
            if order.status in STATUS_FLOW:
                idx = STATUS_FLOW.index(order.status)
                if idx + 1 < len(STATUS_FLOW):
                    next_status = STATUS_FLOW[idx + 1]
                    can_advance = True
                    if next_status == OrderStatus.AWAITING_DELIVER and not order.tracking_number and not _is_pickup(order):
                        can_advance = False
                        advance_block_reason = "Укажите трек-номер перед отгрузкой (кроме самовывоза)."

            context = {
                "request": request,
                "order": order,
                "history": history,
                "payments": payments,
                "past_orders_count": past_orders_count,
                "status_labels": STATUS_LABELS_RU,
                "status_badge_class": STATUS_BADGE_CLASS,
                "payment_status_labels": PAYMENT_STATUS_LABELS_RU,
                "return_status_labels": RETURN_STATUS_LABELS_RU,
                "next_status": next_status,
                "next_status_label": NEXT_STATUS_LABEL.get(next_status) if next_status else None,
                "can_advance": can_advance,
                "advance_block_reason": advance_block_reason,
                "can_cancel": order.status in CAN_CANCEL_STATUSES,
                "can_return": order.status == OrderStatus.DELIVERED,
            }
            return await self.templates.TemplateResponse(request, "orders/detail.html", context)
        finally:
            db.close()

    @expose("/orders/{order_id}/fields", methods=["POST"], identity="orders_fields")
    async def update_fields(self, request: Request) -> Response:
        """Трек-номер / пункт выдачи / служебная заметка — правятся прямо в
        карточке, без похода в отдельную форму: это не переход статуса, у
        ProductAdmin/AdminUserAdmin такая же прямая правка полей формой."""
        order_id = int(request.path_params["order_id"])
        redirect_to = str(request.url_for("admin:view-orders_detail", order_id=order_id))
        form = await request.form()

        db = SessionLocal()
        try:
            order = db.get(Order, order_id)
            if not order:
                raise HTTPException(status_code=404, detail="Заказ не найден")
            order.tracking_number = (form.get("tracking_number") or "").strip()
            order.pickup_point = (form.get("pickup_point") or "").strip()
            order.admin_comment = (form.get("admin_comment") or "").strip()
            db.commit()
            Flash.success(request, "Сохранено.")
        finally:
            db.close()
        return RedirectResponse(redirect_to, status_code=303)

    @expose("/orders/{order_id}/status", methods=["POST"], identity="orders_advance")
    async def advance_status(self, request: Request) -> Response:
        order_id = int(request.path_params["order_id"])
        redirect_to = str(request.url_for("admin:view-orders_detail", order_id=order_id))
        db = SessionLocal()
        try:
            order = db.get(Order, order_id)
            if not order:
                raise HTTPException(status_code=404, detail="Заказ не найден")
            if order.status not in STATUS_FLOW or STATUS_FLOW.index(order.status) + 1 >= len(STATUS_FLOW):
                Flash.error(request, "Из этого статуса нет следующего шага кнопкой.")
                return RedirectResponse(redirect_to, status_code=303)

            next_status = STATUS_FLOW[STATUS_FLOW.index(order.status) + 1]
            if next_status == OrderStatus.AWAITING_DELIVER and not order.tracking_number and not _is_pickup(order):
                Flash.error(request, "Укажите трек-номер перед отгрузкой (кроме самовывоза).")
                return RedirectResponse(redirect_to, status_code=303)

            old_status = order.status
            order.status = next_status
            record_order_status_change(db, order, old_status, order.status, changed_by=_changed_by(request))
            db.commit()
            Flash.success(request, f"Заказ {order.number}: статус — «{STATUS_LABELS_RU[next_status]}».")
        finally:
            db.close()
        return RedirectResponse(redirect_to, status_code=303)

    @expose("/orders/{order_id}/cancel", methods=["POST"], identity="orders_cancel")
    async def cancel_order_route(self, request: Request) -> Response:
        order_id = int(request.path_params["order_id"])
        redirect_to = str(request.url_for("admin:view-orders_detail", order_id=order_id))
        form = await request.form()
        reason = (form.get("reason") or "").strip()
        restock = form.get("restock") == "on"

        db = SessionLocal()
        try:
            order = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
            if not order:
                raise HTTPException(status_code=404, detail="Заказ не найден")
            if order.status not in CAN_CANCEL_STATUSES:
                Flash.error(request, "Этот заказ уже нельзя отменить (в пути, доставлен или уже отменён/возвращён).")
                return RedirectResponse(redirect_to, status_code=303)
            if not reason:
                Flash.error(request, "Укажите причину отмены.")
                return RedirectResponse(redirect_to, status_code=303)

            changed_by = _changed_by(request)
            old_status = order.status
            # Остаток списывается только начиная с awaiting_packaging (см.
            # routers/orders.py:pay_order) — если отменяем ещё неоплаченный
            # заказ, списания не было и возвращать на склад нечего.
            stock_was_deducted = old_status != OrderStatus.AWAITING_PAYMENT
            if restock and stock_was_deducted:
                for item in order.items:
                    product = db.get(Product, item.product_id)
                    if product and product.stock is not None:
                        product.stock += item.quantity
                        db.add(
                            StockMovement(
                                product_id=product.id,
                                delta=item.quantity,
                                reason=StockMovementReason.ORDER_CANCELLED,
                                order_id=order.id,
                                changed_by=changed_by,
                            )
                        )

            order.status = OrderStatus.CANCELLED
            order.cancel_reason = reason
            record_order_status_change(db, order, old_status, order.status, changed_by=changed_by, note=reason)
            db.commit()
            Flash.success(request, f"Заказ {order.number} отменён.")
        finally:
            db.close()
        return RedirectResponse(redirect_to, status_code=303)

    @expose("/orders/{order_id}/return", methods=["POST"], identity="orders_return")
    async def create_return_route(self, request: Request) -> Response:
        order_id = int(request.path_params["order_id"])
        redirect_to = str(request.url_for("admin:view-orders_detail", order_id=order_id))
        form = await request.form()
        reason = (form.get("reason") or "").strip()

        db = SessionLocal()
        try:
            order = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
            if not order:
                raise HTTPException(status_code=404, detail="Заказ не найден")
            if order.status != OrderStatus.DELIVERED:
                Flash.error(request, "Оформить возврат можно только для доставленного заказа.")
                return RedirectResponse(redirect_to, status_code=303)
            if not reason:
                Flash.error(request, "Укажите причину возврата.")
                return RedirectResponse(redirect_to, status_code=303)

            changed_by = _changed_by(request)
            db.add(Return(order_id=order.id, reason=reason, status=ReturnStatus.REQUESTED))
            for item in order.items:
                product = db.get(Product, item.product_id)
                if product and product.stock is not None:
                    product.stock += item.quantity
                    db.add(
                        StockMovement(
                            product_id=product.id,
                            delta=item.quantity,
                            reason=StockMovementReason.RETURNED,
                            order_id=order.id,
                            changed_by=changed_by,
                        )
                    )

            old_status = order.status
            order.status = OrderStatus.RETURNED
            record_order_status_change(db, order, old_status, order.status, changed_by=changed_by, note=reason)
            db.commit()
            Flash.success(request, f"Возврат по заказу {order.number} оформлен.")
        finally:
            db.close()
        return RedirectResponse(redirect_to, status_code=303)

    @expose("/orders/bulk", methods=["POST"], identity="orders_bulk")
    async def bulk_action(self, request: Request) -> Response:
        form = await request.form()
        ids = [int(v) for v in form.getlist("ids") if str(v).isdigit()]
        action = form.get("do")
        redirect_to = request.headers.get("referer") or str(request.url_for("admin:view-orders_list"))

        if not ids:
            Flash.error(request, "Сначала выберите заказы галочками.")
            return RedirectResponse(redirect_to, status_code=303)

        db = SessionLocal()
        try:
            if action == "packaging":
                changed_by = _changed_by(request)
                moved = skipped = no_tracking = 0
                orders = (
                    db.query(Order).options(joinedload(Order.delivery_method)).filter(Order.id.in_(ids)).all()
                )
                for order in orders:
                    if order.status != OrderStatus.AWAITING_PACKAGING:
                        skipped += 1
                        continue
                    if not order.tracking_number and not _is_pickup(order):
                        no_tracking += 1
                        continue
                    old_status = order.status
                    order.status = OrderStatus.AWAITING_DELIVER
                    record_order_status_change(db, order, old_status, order.status, changed_by=changed_by)
                    moved += 1
                db.commit()
                msg = f"Собрано и готово к отгрузке: {moved}."
                if no_tracking:
                    msg += f" Без трек-номера (пропущены): {no_tracking}."
                if skipped:
                    msg += f" Не в статусе «Ожидают сборки» (пропущены): {skipped}."
                Flash.success(request, msg)
            else:
                Flash.error(request, "Неизвестное массовое действие.")
        finally:
            db.close()
        return RedirectResponse(redirect_to, status_code=303)

    @expose("/orders/export.csv", methods=["GET"], identity="orders_export_csv")
    async def export_csv(self, request: Request) -> Response:
        db = SessionLocal()
        try:
            orders = (
                _apply_filters(
                    db.query(Order).options(joinedload(Order.items)), request.query_params
                )
                .order_by(Order.id.desc())
                .all()
            )
            buffer = io.StringIO()
            writer = csv.writer(buffer, delimiter=";")
            writer.writerow(
                ["Номер", "Дата", "Покупатель", "Контакт", "Статус", "Оплата", "Товаров, шт.", "Сумма", "Скидка", "Промокод", "Трек-номер"]
            )
            for o in orders:
                writer.writerow(
                    [
                        o.number,
                        o.created_at.strftime("%d.%m.%Y %H:%M") if o.created_at else "",
                        o.customer_name,
                        o.customer_contact,
                        STATUS_LABELS_RU.get(o.status, o.status.value),
                        PAYMENT_STATUS_LABELS_RU.get(o.payment_status, o.payment_status.value),
                        sum(i.quantity for i in o.items),
                        str(o.total),
                        str(o.discount_total or 0),
                        o.promo_code or "",
                        o.tracking_number,
                    ]
                )
            data = buffer.getvalue().encode("utf-8-sig")  # BOM — чтобы Excel сам понял кодировку
            return StreamingResponse(
                io.BytesIO(data),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=orders.csv"},
            )
        finally:
            db.close()

    @expose("/orders/export.xlsx", methods=["GET"], identity="orders_export_xlsx")
    async def export_xlsx(self, request: Request) -> Response:
        db = SessionLocal()
        try:
            orders = (
                _apply_filters(
                    db.query(Order).options(joinedload(Order.items)), request.query_params
                )
                .order_by(Order.id.desc())
                .all()
            )
            wb = Workbook()
            ws = wb.active
            ws.title = "Заказы"
            ws.append(
                ["Номер", "Дата", "Покупатель", "Контакт", "Статус", "Оплата", "Товаров, шт.", "Сумма", "Скидка", "Промокод", "Трек-номер"]
            )
            for o in orders:
                ws.append(
                    [
                        o.number,
                        o.created_at.strftime("%d.%m.%Y %H:%M") if o.created_at else "",
                        o.customer_name,
                        o.customer_contact,
                        STATUS_LABELS_RU.get(o.status, o.status.value),
                        PAYMENT_STATUS_LABELS_RU.get(o.payment_status, o.payment_status.value),
                        sum(i.quantity for i in o.items),
                        float(o.total),
                        float(o.discount_total or 0),
                        o.promo_code or "",
                        o.tracking_number,
                    ]
                )
            buffer = io.BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            return StreamingResponse(
                buffer,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": "attachment; filename=orders.xlsx"},
            )
        finally:
            db.close()

    @expose("/orders/{order_id}/label.pdf", methods=["GET"], identity="orders_label_pdf")
    async def label_pdf(self, request: Request) -> Response:
        order_id = int(request.path_params["order_id"])
        db = SessionLocal()
        try:
            order = db.query(Order).options(joinedload(Order.delivery_method)).filter(Order.id == order_id).first()
            if not order:
                raise HTTPException(status_code=404, detail="Заказ не найден")
            buffer = io.BytesIO()
            font, supports_cyrillic = _resolve_label_font()
            c = canvas.Canvas(buffer, pagesize=(_LABEL_WIDTH_MM * mm, _LABEL_HEIGHT_MM * mm))
            _draw_label(c, order, font, supports_cyrillic)
            c.showPage()
            c.save()
            buffer.seek(0)
            # Content-Disposition обязан быть latin-1 (см. RFC 6266) — order.number
            # содержит кириллицу («ЧТ-2026-...»), поэтому в имя файла его нельзя,
            # только order.id (ASCII).
            return StreamingResponse(
                buffer,
                media_type="application/pdf",
                headers={"Content-Disposition": f"inline; filename=label-{order.id}.pdf"},
            )
        finally:
            db.close()

    @expose("/orders/labels.pdf", methods=["GET"], identity="orders_labels_pdf_bulk")
    async def labels_pdf_bulk(self, request: Request) -> Response:
        # ids приходит либо как чекбоксы GET-формы (?ids=1&ids=2, см.
        # templates/orders/list.html), либо как одна строка через запятую —
        # принимаем оба варианта.
        raw_ids = request.query_params.getlist("ids")
        if len(raw_ids) == 1 and "," in raw_ids[0]:
            raw_ids = raw_ids[0].split(",")
        ids = [int(v) for v in raw_ids if v.strip().isdigit()]
        if not ids:
            raise HTTPException(status_code=400, detail="Не выбраны заказы")
        db = SessionLocal()
        try:
            orders = db.query(Order).options(joinedload(Order.delivery_method)).filter(Order.id.in_(ids)).all()
            buffer = io.BytesIO()
            font, supports_cyrillic = _resolve_label_font()
            c = canvas.Canvas(buffer, pagesize=(_LABEL_WIDTH_MM * mm, _LABEL_HEIGHT_MM * mm))
            for order in orders:
                _draw_label(c, order, font, supports_cyrillic)
                c.showPage()
            c.save()
            buffer.seek(0)
            return StreamingResponse(
                buffer,
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=labels.pdf"},
            )
        finally:
            db.close()


# --- PDF-этикетки: 58×40 мм (см. ТЗ) --------------------------------------

_LABEL_WIDTH_MM, _LABEL_HEIGHT_MM = 58, 40


def _resolve_label_font() -> tuple[str, bool]:
    """(имя_шрифта, поддерживает_кириллицу). reportlab из коробки знает
    только Base14-шрифты без кириллицы — пытаемся найти на диске TTF с
    кириллицей (Windows — для локальной разработки, Debian/Ubuntu — для
    Render); не нашли — печатаем транслитом на Helvetica, лишь бы этикетка не
    сломалась. TODO(labels): положить свой .ttf в репозиторий (например
    DejaVuSans) вместо угадывания путей — надёжнее, чем зависеть от того, что
    случайно стоит на хосте."""
    if "LabelFont" in pdfmetrics.getRegisteredFontNames():
        return "LabelFont", True
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("LabelFont", path))
                return "LabelFont", True
            except Exception:
                continue
    return "Helvetica", False


_TRANSLIT = str.maketrans(
    {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
        "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
        "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
        "э": "e", "ю": "yu", "я": "ya",
        "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "E", "Ж": "Zh", "З": "Z", "И": "I",
        "Й": "Y", "К": "K", "Л": "L", "М": "M", "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T",
        "У": "U", "Ф": "F", "Х": "Kh", "Ц": "Ts", "Ч": "Ch", "Ш": "Sh", "Щ": "Shch", "Ъ": "", "Ы": "Y", "Ь": "",
        "Э": "E", "Ю": "Yu", "Я": "Ya", "№": "No",
    }
)


def _label_text(text: str, supports_cyrillic: bool) -> str:
    return text if supports_cyrillic else text.translate(_TRANSLIT)


def _wrap_text(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:3]  # этикетка маленькая — больше 3 строк адреса не влезет


def _draw_label(c: canvas.Canvas, order: Order, font: str, supports_cyrillic: bool) -> None:
    h = _LABEL_HEIGHT_MM * mm

    def t(s: str) -> str:
        return _label_text(s, supports_cyrillic)

    y = h - 5 * mm
    c.setFont(font, 9)
    c.drawString(3 * mm, y, t(f"«Чтиво» — заказ {order.number}"))
    y -= 5 * mm
    c.setFont(font, 7)
    c.drawString(3 * mm, y, t(order.created_at.strftime("%d.%m.%Y %H:%M") if order.created_at else ""))
    y -= 5 * mm
    c.drawString(3 * mm, y, t(f"Получатель: {order.customer_name or '—'}"))
    y -= 4 * mm
    c.drawString(3 * mm, y, t(f"Контакт: {order.customer_contact or '—'}"))
    y -= 4 * mm
    method_name = order.delivery_method.name if order.delivery_method else "—"
    c.drawString(3 * mm, y, t(f"Доставка: {method_name}"))
    y -= 4 * mm
    address = order.pickup_point or order.delivery_address or "—"
    for line in _wrap_text(t(address), 34):
        c.drawString(3 * mm, y, line)
        y -= 3.6 * mm
    if order.tracking_number:
        c.setFont(font, 8)
        c.drawString(3 * mm, 3 * mm, t(f"Трек: {order.tracking_number}"))
