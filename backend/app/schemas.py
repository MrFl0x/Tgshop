from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from .models import (
    DeliveryCostType,
    DiscountType,
    OrderStatus,
    PaymentStatus,
    ProductType,
    ReturnStatus,
    StockMovementReason,
)


class AddressIn(BaseModel):
    label: str = ""
    text: str
    is_default: bool = False


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    text: str
    is_default: bool


class CustomerOut(BaseModel):
    """Профиль клиента — экран «Профиль» в Mini App (ТЗ-3 п.3). Read-only:
    отдаёт то, что уже накопилось на клиенте, не заводит нового — см.
    routers/customers.py:get_profile."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    contact: str
    referral_code: Optional[str]
    bonus_balance: Decimal


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    type: ProductType
    description: str
    cover_url: str
    price: Decimal
    stock: Optional[int]
    is_active: bool


class StockMovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    delta: int
    reason: StockMovementReason
    order_id: Optional[int]
    note: str
    changed_by: str
    created_at: datetime


class DeliveryMethodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: str
    cost_type: DeliveryCostType
    fixed_cost: Optional[Decimal]
    requires_address: bool
    is_active: bool


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int = 1


class OrderCreateIn(BaseModel):
    # telegram_id сюда больше не входит (ТЗ-3 п.4) — backend берёт его из
    # проверенного initData (см. app/telegram_auth.py, ТЗ-0), а не из тела
    # запроса: то поле легко подделать, доверять ему для привязки заказа к
    # клиенту нельзя.
    referral_code: Optional[str] = None  # код пригласившего, если клиент новый
    customer_name: str
    customer_contact: str
    delivery_method_id: int
    delivery_address: str = ""       # свободный ввод; игнорируется, если указан address_id
    address_id: Optional[int] = None  # адрес из сохранённых (см. /customers/{telegram_id}/addresses)
    promo_code: Optional[str] = None  # см. app/models.py:PromoCode — применяется в create_order
    customer_comment: str = ""
    items: List[OrderItemIn]


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    title: str
    price: Decimal
    quantity: int
    subtotal: Decimal


class ReturnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reason: str
    status: ReturnStatus
    comment: str
    created_at: datetime


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    customer_id: Optional[int]
    customer_name: str
    customer_contact: str
    delivery_method_id: int
    delivery_address: str
    address_id: Optional[int]
    pickup_point: str
    delivery_cost: Decimal
    items_total: Decimal
    discount_total: Decimal
    promo_code: Optional[str]
    total: Decimal
    status: OrderStatus
    payment_status: PaymentStatus
    payment_method: str
    tracking_number: str
    customer_comment: str
    cancel_reason: str
    created_at: datetime
    items: List[OrderItemOut]
    returns: List[ReturnOut] = []


class OrderStatusHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: Optional[OrderStatus]
    to_status: OrderStatus
    changed_by: str
    note: str
    created_at: datetime


class PromoCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    discount_type: DiscountType
    discount_value: Decimal
