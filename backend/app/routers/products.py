from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Product, StockMovement
from ..schemas import ProductOut, StockMovementOut

router = APIRouter(prefix="/products", tags=["Каталог"])


@router.get("/", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)):
    """Каталог для витрины — только активные товары."""
    stmt = select(Product).where(Product.is_active.is_(True)).order_by(Product.id.desc())
    return db.scalars(stmt).all()


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return product


@router.get("/{product_id}/stock-history", response_model=List[StockMovementOut])
def get_stock_history(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return db.scalars(
        select(StockMovement).where(StockMovement.product_id == product_id).order_by(StockMovement.id.desc())
    ).all()
