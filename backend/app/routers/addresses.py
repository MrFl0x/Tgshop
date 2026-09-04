"""
Адресная книга клиента: сохранить адрес один раз и переиспользовать его в
следующих заказах/подписках (см. Order.address_id, Subscription.address_id).

telegram_id в пути оставлен для читаемости URL, но источником истины больше
не является (см. docs/TZ-02-bot-i-miniapp.md, ТЗ-0): реальный telegram_id
берётся из подписанного initData (заголовок X-Telegram-Init-Data, см.
app/telegram_auth.py) и сверяется с тем, что указан в пути — при
расхождении запрос отклоняется, а не выполняется от чужого имени.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..customers import get_or_create_customer
from ..database import get_db
from ..models import Address, Customer
from ..schemas import AddressIn, AddressOut
from ..telegram_auth import get_verified_telegram_id

router = APIRouter(prefix="/customers/{telegram_id}/addresses", tags=["Адреса"])


def _require_owner(telegram_id: str, verified_telegram_id: str) -> None:
    if telegram_id != verified_telegram_id:
        raise HTTPException(status_code=403, detail="telegram_id в пути не совпадает с initData")


@router.get("/", response_model=List[AddressOut])
def list_addresses(
    telegram_id: str,
    db: Session = Depends(get_db),
    verified_telegram_id: str = Depends(get_verified_telegram_id),
):
    _require_owner(telegram_id, verified_telegram_id)
    customer = db.scalar(select(Customer).where(Customer.telegram_id == telegram_id))
    if not customer:
        return []
    return db.scalars(
        select(Address)
        .where(Address.customer_id == customer.id)
        .order_by(Address.is_default.desc(), Address.id.desc())
    ).all()


@router.post("/", response_model=AddressOut)
def create_address(
    telegram_id: str,
    payload: AddressIn,
    db: Session = Depends(get_db),
    verified_telegram_id: str = Depends(get_verified_telegram_id),
):
    _require_owner(telegram_id, verified_telegram_id)
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Адрес не может быть пустым")

    # get_or_create — чтобы адрес можно было сохранить и до первого заказа
    # (бот уже знает telegram_id из чата, заказа ещё не было).
    customer = get_or_create_customer(db, telegram_id=telegram_id, full_name="", contact="")

    if payload.is_default:
        db.query(Address).filter(Address.customer_id == customer.id).update({"is_default": False})

    address = Address(
        customer_id=customer.id,
        label=payload.label,
        text=payload.text.strip(),
        is_default=payload.is_default,
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


@router.delete("/{address_id}", status_code=204)
def delete_address(
    telegram_id: str,
    address_id: int,
    db: Session = Depends(get_db),
    verified_telegram_id: str = Depends(get_verified_telegram_id),
):
    _require_owner(telegram_id, verified_telegram_id)
    customer = db.scalar(select(Customer).where(Customer.telegram_id == telegram_id))
    address = db.get(Address, address_id) if customer else None
    if not customer or not address or address.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="Адрес не найден")
    db.delete(address)
    db.commit()
