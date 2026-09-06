"""
Модели данных. Один источник правды для каталога, доставки и заказов —
и админ-панель (app/admin.py), и API (app/routers/*) читают/пишут через них.
"""
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from fastapi_storages.integrations.sqlalchemy import ImageType
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship

from .database import Base
from .media import product_images_storage


class ProductType(str, enum.Enum):
    ISSUE = "issue"                # отдельный печатный номер
    SUBSCRIPTION = "subscription"  # подписка на период
    MERCH = "merch"                # мерч и допродукты


class DeliveryCostType(str, enum.Enum):
    FREE = "free"              # бесплатно (самовывоз)
    FIXED = "fixed"            # фиксированная стоимость
    CALCULATED = "calculated"  # считается через API службы — сейчас заглушка на fixed_cost


class OrderStatus(str, enum.Enum):
    NEW = "new"
    PAID = "paid"
    ASSEMBLED = "assembled"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class BonusReason(str, enum.Enum):
    REFERRAL_INVITER = "referral_inviter"  # бонус пригласившему
    REFERRAL_INVITEE = "referral_invitee"  # бонус приглашённому
    MANUAL = "manual"                      # ручная корректировка редакцией


class StockMovementReason(str, enum.Enum):
    SALE = "sale"                        # списание при оплате заказа
    ORDER_CANCELLED = "order_cancelled"  # возврат на склад при отмене уже оплаченного заказа
    RESTOCK = "restock"                  # приход — редактор увеличил остаток в форме товара
    CORRECTION = "correction"            # инвентаризация/коррекция — редактор уменьшил остаток


class Address(Base):
    """Адресная книга клиента — чтобы не вводить адрес заново при каждом
    заказе/подписке. `Order.delivery_address` и `Subscription.delivery_address`
    остаются снимком текста на момент оформления (как `OrderItem.price`);
    `address_id` — необязательная ссылка на запись отсюда, если адрес был
    выбран из сохранённых, а не введён заново."""

    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    label = Column(String(50), nullable=False, default="")  # "Дом", "Работа" — для выбора в списке
    text = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer")

    def __str__(self) -> str:
        return self.label or (self.text[:40] + "…" if len(self.text) > 40 else self.text)


class AdminUser(Base):
    """Аккаунт редактора для входа в /admin. Раньше был один общий логин из
    ADMIN_USERNAME/ADMIN_PASSWORD (.env) — теперь эти переменные используются
    только для бутстрапа первой записи здесь (см. app/seed.py), а новых
    редакторов заводят через саму панель («Редакторы»). Личные логины нужны,
    чтобы в OrderStatusHistory.changed_by было видно, кто именно менял статус
    заказа, а не просто "admin"."""

    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # см. app/security.py — pbkdf2, соли, без внешних зависимостей
    full_name = Column(String(255), nullable=False, default="")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    def __str__(self) -> str:
        return self.username


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    type = Column(SAEnum(ProductType), nullable=False, default=ProductType.ISSUE)
    description = Column(Text, nullable=False, default="")
    cover_url = Column(String(500), nullable=False, default="")
    # Файл обложки, загружаемый редактором прямо из формы в /admin (см.
    # ProductAdmin в app/admin.py) — после сохранения его публичный URL
    # копируется в cover_url, который и читает Mini App (routers/products.py,
    # ProductCard.tsx). cover_url остаётся текстовым полем — можно по-прежнему
    # просто вставить внешнюю ссылку на картинку, не загружая файл.
    image_upload = Column(ImageType(storage=product_images_storage, upload_to="products"), nullable=True)
    price = Column(Numeric(10, 2), nullable=False, default=0)
    stock = Column(Integer, nullable=True)  # null = без ограничения (например, подписка)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __str__(self) -> str:
        return self.title


class StockMovement(Base):
    """Журнал изменений Product.stock — склад-заглушка на одну физическую
    точку (офис редакции), без учёта нескольких мест хранения; если появится
    второй склад, сюда добавится warehouse_id. Каждое изменение остатка
    должно сопровождаться записью здесь: автоматически при оплате заказа и
    при отмене уже оплаченного (см. routers/orders.py, app/admin.py), либо
    когда редактор правит Product.stock вручную в форме товара —
    ProductAdmin сам считает разницу и логирует её как приход/коррекцию."""

    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    delta = Column(Integer, nullable=False)  # положительное — приход, отрицательное — списание
    reason = Column(SAEnum(StockMovementReason), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    note = Column(Text, nullable=False, default="")
    changed_by = Column(String(120), nullable=False, default="system")
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product")
    order = relationship("Order")

    def __str__(self) -> str:
        sign = "+" if self.delta > 0 else ""
        return f"Товар №{self.product_id}: {sign}{self.delta} ({self.reason.value})"


class DeliveryMethod(Base):
    __tablename__ = "delivery_methods"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)             # "СДЭК — курьером"
    code = Column(String(50), nullable=False, unique=True)  # "cdek_courier"
    description = Column(Text, nullable=False, default="")
    cost_type = Column(SAEnum(DeliveryCostType), nullable=False, default=DeliveryCostType.FIXED)
    fixed_cost = Column(Numeric(10, 2), nullable=True, default=0)
    requires_address = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0)

    def __str__(self) -> str:
        return self.name


class Customer(Base):
    """Читатель Telegram-магазина. Заводится автоматически при первом заказе,
    если бот передал telegram_id — так заказы можно связывать в историю
    покупок одного человека для ретеншна (сегменты, реферальная программа)."""

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(32), unique=True, nullable=True, index=True)
    full_name = Column(String(255), nullable=False, default="")
    contact = Column(String(255), nullable=False, default="")  # телефон или @username
    referral_code = Column(String(16), unique=True, nullable=True, index=True)
    referred_by_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    bonus_balance = Column(Numeric(10, 2), default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    referred_by = relationship("Customer", remote_side=[id])

    def __str__(self) -> str:
        return self.full_name or self.contact or f"Клиент №{self.id}"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    delivery_method_id = Column(Integer, ForeignKey("delivery_methods.id"), nullable=False)
    delivery_address = Column(Text, nullable=False, default="")
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=True)
    status = Column(SAEnum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False)
    auto_renew = Column(Boolean, default=True, nullable=False)
    current_period_end = Column(DateTime, nullable=True)
    cancel_reason = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer")
    product = relationship("Product")
    delivery_method = relationship("DeliveryMethod")
    address = relationship("Address")

    def __str__(self) -> str:
        return f"Подписка №{self.id}"


class PaymentTransaction(Base):
    """Журнал попыток оплаты — отдельно от Order.payment_status, чтобы был
    аудиторский след (в т.ч. для сверки с ЮKassa, когда подключим её вместо
    заглушки: несколько попыток на один заказ, ретраи, возвраты)."""

    __tablename__ = "payment_transactions"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    provider = Column(String(50), nullable=False, default="stub")
    provider_payment_id = Column(String(120), nullable=False, default="")
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(SAEnum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False)
    note = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order")
    subscription = relationship("Subscription")

    def __str__(self) -> str:
        return f"Транзакция №{self.id}"


class BonusTransaction(Base):
    """Начисления и списания бонусного счёта клиента — минимальная версия
    реферальной программы: видно, кому и за что начислено."""

    __tablename__ = "bonus_transactions"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)  # отрицательное значение — списание
    reason = Column(SAEnum(BonusReason), nullable=False, default=BonusReason.MANUAL)
    related_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer")

    def __str__(self) -> str:
        return f"Бонус №{self.id}"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_name = Column(String(255), nullable=False, default="")
    customer_contact = Column(String(255), nullable=False, default="")  # телефон или @username в Telegram
    delivery_method_id = Column(Integer, ForeignKey("delivery_methods.id"), nullable=False)
    delivery_address = Column(Text, nullable=False, default="")
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=True)
    delivery_cost = Column(Numeric(10, 2), default=0)
    items_total = Column(Numeric(10, 2), default=0)
    total = Column(Numeric(10, 2), default=0)
    status = Column(SAEnum(OrderStatus), default=OrderStatus.NEW, nullable=False)
    payment_status = Column(SAEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    tracking_number = Column(String(120), nullable=False, default="")
    cancel_reason = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer")
    delivery_method = relationship("DeliveryMethod")
    address = relationship("Address")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    def __str__(self) -> str:
        return f"Заказ №{self.id}"


class OrderStatusHistory(Base):
    """Журнал переходов Order.status — кто и когда перевёл заказ
    new → paid → assembled → shipped → delivered (или cancelled). Пишется в
    двух местах одной функцией (app/order_history.py): routers/orders.py
    (автоматически при оплате) и app/admin.py (когда статус меняет редактор
    вручную) — раньше был виден только текущий статус без истории."""

    __tablename__ = "order_status_history"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    from_status = Column(SAEnum(OrderStatus), nullable=True)  # null — самая первая запись
    to_status = Column(SAEnum(OrderStatus), nullable=False)
    changed_by = Column(String(120), nullable=False, default="system")  # логин редактора (AdminUser.username) или "system"
    note = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order")

    def __str__(self) -> str:
        return f"Заказ №{self.order_id}: {self.from_status} → {self.to_status}"


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    title = Column(String(255), nullable=False)     # снимок названия на момент заказа
    price = Column(Numeric(10, 2), nullable=False)  # снимок цены на момент заказа
    quantity = Column(Integer, nullable=False, default=1)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")
