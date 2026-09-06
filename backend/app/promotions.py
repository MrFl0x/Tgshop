"""
Промокоды на скидку (см. app/models.py:PromoCode, tz-zakazy.md). Один общий
расчёт скидки — чтобы предпросмотр в routers/promo_codes.py (до отправки
заказа) и применение в routers/orders.py:create_order (уже на сервере,
источник истины) не могли разойтись в формуле.
"""
from datetime import datetime
from decimal import Decimal

from .models import DiscountType, PromoCode


def is_promo_valid(promo: PromoCode | None) -> bool:
    if not promo or not promo.is_active:
        return False
    if promo.valid_until and promo.valid_until < datetime.utcnow():
        return False
    return True


def promo_discount(promo: PromoCode, items_total: Decimal) -> Decimal:
    """Скидка в ₽ от суммы товаров (без учёта доставки — как в ТЗ, строка
    "Скидка по промокоду -10%" считается от строки "Товары"). Не уводит итог
    в минус — скидка не может превышать items_total."""
    if promo.discount_type == DiscountType.PERCENT:
        raw = items_total * Decimal(promo.discount_value) / Decimal(100)
    else:
        raw = Decimal(promo.discount_value)
    return min(raw, items_total)
