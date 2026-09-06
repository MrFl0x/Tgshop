from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PromoCode
from ..schemas import PromoCodeOut

router = APIRouter(prefix="/promo-codes", tags=["Промокоды"])


@router.get("/{code}", response_model=PromoCodeOut)
def get_promo_code(code: str, db: Session = Depends(get_db)):
    """Публичный, без initData — как каталог: сам код клиенту ничего не даёт,
    это чтение существующего промокода. Mini App вызывает это на экране
    оформления, чтобы показать скидку ДО отправки заказа; окончательная
    проверка и расчёт — ещё раз на сервере, в routers/orders.py:create_order,
    этому эндпоинту доверия при создании заказа нет."""
    promo = db.query(PromoCode).filter(func.upper(PromoCode.code) == code.strip().upper()).first()
    if not promo or not promo.is_active or (promo.valid_until and promo.valid_until < datetime.utcnow()):
        raise HTTPException(status_code=404, detail="Промокод не найден или недействителен")
    return promo
