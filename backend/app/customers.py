"""
Логика вокруг клиента: найти-или-создать по telegram_id, выдать реферальный
код, начислить бонус за приглашение. Вынесено из роутера заказов, чтобы
routers/orders.py оставался про заказ, а не про CRM.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import BonusReason, BonusTransaction, Customer

# MVP-константы бонуса за реферал. Пока не вынесены в админку — сделать
# настраиваемыми в этапе 05 (подписка и ретеншн), если понадобится гибкость.
REFERRAL_BONUS_INVITER = Decimal("200")
REFERRAL_BONUS_INVITEE = Decimal("200")


def _make_referral_code(customer_id: int) -> str:
    return f"CHT{customer_id:05d}"


def get_or_create_customer(
    db: Session,
    *,
    telegram_id: str | None,
    full_name: str,
    contact: str,
    referral_code: str | None = None,
) -> Customer:
    """Возвращает существующего клиента по telegram_id либо создаёт нового.
    Без telegram_id (например, гостевой заказ через /docs) — всегда новый
    анонимный клиент."""
    customer = None
    if telegram_id:
        customer = db.scalar(select(Customer).where(Customer.telegram_id == telegram_id))

    if customer:
        customer.last_seen_at = datetime.utcnow()
        # Профиль могли уточнить (например, указали имя при заказе) — обновляем мягко.
        if full_name and not customer.full_name:
            customer.full_name = full_name
        if contact and not customer.contact:
            customer.contact = contact
        return customer

    referred_by = None
    if referral_code:
        referred_by = db.scalar(select(Customer).where(Customer.referral_code == referral_code))

    customer = Customer(
        telegram_id=telegram_id,
        full_name=full_name,
        contact=contact,
        referred_by_id=referred_by.id if referred_by else None,
    )
    db.add(customer)
    db.flush()  # нужен customer.id для реферального кода
    customer.referral_code = _make_referral_code(customer.id)
    return customer


def award_referral_bonus_if_eligible(db: Session, customer: Customer, order_id: int) -> None:
    """Начисляет бонус пригласившему и приглашённому при первом оплаченном
    заказе приглашённого. Идемпотентно: проверяет, не начисляли ли уже."""
    if not customer.referred_by_id:
        return

    already_awarded = db.scalar(
        select(BonusTransaction).where(
            BonusTransaction.customer_id == customer.id,
            BonusTransaction.reason == BonusReason.REFERRAL_INVITEE,
        )
    )
    if already_awarded:
        return

    inviter = db.get(Customer, customer.referred_by_id)
    if not inviter:
        return

    customer.bonus_balance = (customer.bonus_balance or 0) + REFERRAL_BONUS_INVITEE
    db.add(
        BonusTransaction(
            customer_id=customer.id,
            amount=REFERRAL_BONUS_INVITEE,
            reason=BonusReason.REFERRAL_INVITEE,
            related_order_id=order_id,
        )
    )

    inviter.bonus_balance = (inviter.bonus_balance or 0) + REFERRAL_BONUS_INVITER
    db.add(
        BonusTransaction(
            customer_id=inviter.id,
            amount=REFERRAL_BONUS_INVITER,
            reason=BonusReason.REFERRAL_INVITER,
            related_order_id=order_id,
        )
    )
