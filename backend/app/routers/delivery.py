from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DeliveryMethod
from ..schemas import DeliveryMethodOut

router = APIRouter(prefix="/delivery-methods", tags=["Доставка"])


@router.get("/", response_model=list[DeliveryMethodOut])
def list_delivery_methods(db: Session = Depends(get_db)):
    """Все включённые способы доставки — витрина показывает клиенту выбор,
    а не один захардкоженный вариант."""
    stmt = (
        select(DeliveryMethod)
        .where(DeliveryMethod.is_active.is_(True))
        .order_by(DeliveryMethod.sort_order)
    )
    return db.scalars(stmt).all()
