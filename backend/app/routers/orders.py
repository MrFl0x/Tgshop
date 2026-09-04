from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..customers import award_referral_bonus_if_eligible, get_or_create_customer
from ..database import get_db
from ..models import (
    Address,
    Customer,
    DeliveryCostType,
    DeliveryMethod,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    PaymentStatus,
    PaymentTransaction,
    Product,
    StockMovement,
    StockMovementReason,
    TransactionStatus,
)
from ..order_history import record_order_status_change
from ..payments import get_payment_provider
from ..schemas import OrderCreateIn, OrderOut, OrderStatusHistoryOut
from ..telegram_auth import get_verified_telegram_id

router = APIRouter(prefix="/orders", tags=["Заказы"])


def _get_owned_order(db: Session, order_id: int, telegram_id: str) -> Order:
    """Отдаёт заказ, только если он принадлежит verified telegram_id — иначе
    404 (см. docs/TZ-03-zakryt-dyru-i-miniapp.md, ТЗ-А). Здесь именно 404, а
    не 403, как в routers/addresses.py и routers/customers.py: там telegram_id
    и так открыт в самом пути URL, а тут order_id сам по себе ничего не
    раскрывает — подтверждать чужим запросом «этот заказ существует, но не
    твой» было бы лишней информацией.

    Гостевые заказы (оформленные через /docs без initData, order.customer_id
    is None) закрыты для чтения через API полностью — доступны только в
    /admin. Для нынешнего масштаба это проще, чем вводить отдельный
    секретный токен для гостевого сценария."""
    order = db.get(Order, order_id)
    if not order or order.customer_id is None or order.customer.telegram_id != telegram_id:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    return order


@router.post("/", response_model=OrderOut)
def create_order(
    payload: OrderCreateIn,
    db: Session = Depends(get_db),
    telegram_id: str = Depends(get_verified_telegram_id),
):
    # telegram_id берём только из проверенного initData (см. app/telegram_auth.py,
    # ТЗ-0) — в OrderCreateIn такого поля больше нет (ТЗ-3, п.4).
    delivery = db.get(DeliveryMethod, payload.delivery_method_id)
    if not delivery or not delivery.is_active:
        raise HTTPException(status_code=400, detail="Способ доставки недоступен")
    if delivery.requires_address and not payload.delivery_address.strip() and not payload.address_id:
        raise HTTPException(status_code=400, detail="Для этого способа доставки нужен адрес")
    if not payload.items:
        raise HTTPException(status_code=400, detail="Корзина пуста")

    customer = get_or_create_customer(
        db,
        telegram_id=telegram_id,
        full_name=payload.customer_name,
        contact=payload.customer_contact,
        referral_code=payload.referral_code,
    )

    address = None
    if payload.address_id is not None:
        address = db.get(Address, payload.address_id)
        if not address or address.customer_id != customer.id:
            raise HTTPException(status_code=400, detail="Адрес не найден")

    order = Order(
        customer_id=customer.id,
        customer_name=payload.customer_name,
        customer_contact=payload.customer_contact,
        delivery_method_id=delivery.id,
        delivery_address=payload.delivery_address.strip() or (address.text if address else ""),
        address_id=address.id if address else None,
        status=OrderStatus.NEW,
        payment_status=PaymentStatus.PENDING,
    )

    items_total = 0.0
    for line in payload.items:
        product = db.get(Product, line.product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=400, detail=f"Товар {line.product_id} недоступен")
        if line.quantity < 1:
            raise HTTPException(status_code=400, detail="Количество должно быть больше нуля")
        # Проверяем остаток, но не резервируем его — списание происходит только
        # при оплате (см. pay_order). Значит несколько неоплаченных заказов
        # подряд могут пройти эту проверку на один и тот же последний остаток;
        # для нынешнего объёма продаж это приемлемо. TODO(warehouse): если
        # заказы без оплаты станут массовыми — резервировать остаток здесь с
        # истечением брони (например, через N минут), а не только при оплате.
        if product.stock is not None and product.stock < line.quantity:
            raise HTTPException(status_code=400, detail=f"«{product.title}» — недостаточно остатка")

        order.items.append(
            OrderItem(
                product_id=product.id,
                title=product.title,
                price=product.price,
                quantity=line.quantity,
            )
        )
        items_total += float(product.price) * line.quantity

    # Для CALCULATED пока используем fixed_cost как заглушку — сюда встанет
    # реальный расчёт через API СДЭК/Boxberry/Почты России (см. app/delivery_providers.py, TODO).
    delivery_cost = 0.0 if delivery.cost_type == DeliveryCostType.FREE else float(delivery.fixed_cost or 0)

    order.items_total = items_total
    order.delivery_cost = delivery_cost
    order.total = items_total + delivery_cost

    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.post("/{order_id}/pay", response_model=OrderOut)
def pay_order(
    order_id: int,
    db: Session = Depends(get_db),
    telegram_id: str = Depends(get_verified_telegram_id),
):
    """Заглушка оплаты: подтверждает заказ без реального списания денег.
    Точка замены на ЮKassa, когда будет готов договор — см. app/payments.py.

    Проверка владения (initData) нужна именно на переходный период с
    заглушкой, а не как финальная архитектура: когда подключится ЮKassa,
    этот эндпоинт по-хорошему перестанет быть тем, что вызывает сам клиент —
    платёж будет подтверждать вебхук от ЮKassa (сервер-сервер, с проверкой
    подписи от них, а не initData)."""
    order = _get_owned_order(db, order_id, telegram_id)
    if order.payment_status == PaymentStatus.PAID:
        return order

    old_status = order.status
    provider = get_payment_provider()
    result = provider.charge(order.id, float(order.total))

    db.add(
        PaymentTransaction(
            order_id=order.id,
            provider="stub",  # TODO(payments): брать из get_payment_provider(), когда появится ЮKassa
            provider_payment_id=result.provider_payment_id,
            amount=order.total,
            status=TransactionStatus.SUCCEEDED if result.success else TransactionStatus.FAILED,
            note=result.note,
        )
    )

    if result.success:
        order.payment_status = PaymentStatus.PAID
        order.status = OrderStatus.PAID
        for item in order.items:
            product = db.get(Product, item.product_id)
            if product and product.stock is not None:
                # Не зажимаем в 0: остаток могли раскупить/поправить в админке
                # между созданием заказа и оплатой (стока на резерв нет — см.
                # TODO ниже). Уходим в минус демонстративно — это сигнал
                # редакции, что расхождение нужно разобрать руками, а не
                # тихо спрятанный ноль.
                product.stock -= item.quantity
                db.add(
                    StockMovement(
                        product_id=product.id,
                        delta=-item.quantity,
                        reason=StockMovementReason.SALE,
                        order_id=order.id,
                        changed_by="system",
                    )
                )
        if order.customer_id:
            customer = db.get(Customer, order.customer_id)
            if customer:
                award_referral_bonus_if_eligible(db, customer, order.id)
    else:
        order.payment_status = PaymentStatus.FAILED

    record_order_status_change(db, order, old_status, order.status, changed_by="system", note="Автоматически при оплате")

    db.commit()
    db.refresh(order)
    return order


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    telegram_id: str = Depends(get_verified_telegram_id),
):
    return _get_owned_order(db, order_id, telegram_id)


@router.get("/{order_id}/history", response_model=List[OrderStatusHistoryOut])
def get_order_history(
    order_id: int,
    db: Session = Depends(get_db),
    telegram_id: str = Depends(get_verified_telegram_id),
):
    order = _get_owned_order(db, order_id, telegram_id)
    return db.scalars(
        select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id).order_by(OrderStatusHistory.id)
    ).all()
