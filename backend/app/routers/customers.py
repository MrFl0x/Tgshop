"""
Профиль клиента и список его заказов — экраны «Профиль» и «Мои заказы» в
Mini App (см. docs/TZ-02-bot-i-miniapp.md, ТЗ-3 п.2-3). telegram_id в пути
оставлен для читаемости URL, но источником истины не является — сверяется с
проверенным initData (см. app/telegram_auth.py), как и в routers/addresses.py.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Customer, Order
from ..schemas import CustomerOut, OrderOut
from ..telegram_auth import get_verified_telegram_id

router = APIRouter(prefix="/customers/{telegram_id}", tags=["Клиент"])


def _require_owner(telegram_id: str, verified_telegram_id: str) -> None:
    if telegram_id != verified_telegram_id:
        raise HTTPException(status_code=403, detail="telegram_id в пути не совпадает с initData")


@router.get("", response_model=CustomerOut)
def get_profile(
    telegram_id: str,
    db: Session = Depends(get_db),
    verified_telegram_id: str = Depends(get_verified_telegram_id),
):
    """Read-only — в отличие от get_or_create_customer (app/customers.py,
    вызывается при оформлении заказа) новый клиент здесь не заводится: до
    первого заказа или сохранённого адреса профиля просто ещё нет — 404."""
    _require_owner(telegram_id, verified_telegram_id)
    customer = db.scalar(select(Customer).where(Customer.telegram_id == telegram_id))
    if not customer:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    return customer


@router.get("/orders", response_model=List[OrderOut])
def list_customer_orders(
    telegram_id: str,
    db: Session = Depends(get_db),
    verified_telegram_id: str = Depends(get_verified_telegram_id),
):
    _require_owner(telegram_id, verified_telegram_id)
    customer = db.scalar(select(Customer).where(Customer.telegram_id == telegram_id))
    if not customer:
        return []
    return db.scalars(
        select(Order).where(Order.customer_id == customer.id).order_by(Order.id.desc())
    ).all()
