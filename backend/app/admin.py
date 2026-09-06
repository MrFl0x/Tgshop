"""
Веб-админка редакции на SQLAdmin: добавление/редактирование товаров и
способов доставки без единой строчки кода, плюс панель заказов со статусами
и трек-номером — та же сущность, что описана в продуктовом плане.
"""
import secrets

import wtforms
from sqladmin import Admin, ModelView
from sqladmin.secret import Secret

from .auth import AdminAuth
from .database import SessionLocal
from .media import image_public_url
from .models import (
    Address,
    AdminUser,
    BonusTransaction,
    Customer,
    DeliveryMethod,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    PaymentTransaction,
    Product,
    StockMovement,
    StockMovementReason,
    Subscription,
)
from .order_history import record_order_status_change
from .security import hash_password


class ProductAdmin(ModelView, model=Product):
    name = "Товар"
    name_plural = "Товары"
    icon = "fa-solid fa-book"
    column_list = [Product.id, Product.title, Product.type, Product.price, Product.stock, Product.is_active]
    column_searchable_list = [Product.title]
    column_sortable_list = [Product.id, Product.price, Product.stock]
    # image_upload — файловое поле (виджет-загрузчик подставляется автоматом
    # моделеконвертером sqladmin по типу колонки ImageType, см. models.py).
    # cover_url остаётся рядом как текстовое поле — можно вставить внешнюю
    # ссылку на картинку вместо загрузки файла; при загрузке файла его
    # публичный URL перезаписывает cover_url в after_model_change ниже.
    form_columns = [
        Product.title,
        Product.type,
        Product.description,
        Product.image_upload,
        Product.cover_url,
        Product.price,
        Product.stock,
        Product.is_active,
    ]
    form_args = {
        "image_upload": {"description": "Загрузите файл — публичная ссылка сама подставится в поле «Cover Url» ниже."},
        "cover_url": {"description": "Заполняется автоматически при загрузке файла выше; можно вписать и внешнюю ссылку на картинку вручную."},
    }

    async def on_model_change(self, data: dict, model: Product, is_created: bool, request) -> None:
        # Остаток на затычке: приход/коррекция делаются прямо здесь, правкой
        # числа Product.stock (отдельного экрана "приёмка товара" нет) — но
        # разницу логируем автоматически, чтобы в StockMovement не было дыр.
        if not is_created:
            request.state.product_old_stock = model.stock

    async def after_model_change(self, data: dict, model: Product, is_created: bool, request) -> None:
        changed_by = request.session.get("admin_username") or "admin"
        old_stock = getattr(request.state, "product_old_stock", None)
        stock_changed = old_stock is not None and model.stock is not None and old_stock != model.stock

        db = SessionLocal()
        try:
            # Свежий инстанс в своей сессии: `model.image_upload` на этом шаге
            # ещё может быть "сырым" объектом загрузки, а не сохранённым
            # StorageImage (тип-конвертер applies только к тому, что реально
            # прочитано из БД) — читаем cover_url/image_upload только отсюда.
            product = db.get(Product, model.id)
            new_cover_url = image_public_url(product.image_upload) if product.image_upload else None
            cover_url_changed = new_cover_url is not None and new_cover_url != product.cover_url

            if not stock_changed and not cover_url_changed:
                return

            if stock_changed:
                db.add(
                    StockMovement(
                        product_id=model.id,
                        delta=model.stock - old_stock,
                        reason=StockMovementReason.RESTOCK
                        if model.stock > old_stock
                        else StockMovementReason.CORRECTION,
                        changed_by=changed_by,
                    )
                )
            if cover_url_changed:
                product.cover_url = new_cover_url
            db.commit()
        finally:
            db.close()


class DeliveryMethodAdmin(ModelView, model=DeliveryMethod):
    name = "Способ доставки"
    name_plural = "Способы доставки"
    icon = "fa-solid fa-truck"
    column_list = [
        DeliveryMethod.id,
        DeliveryMethod.name,
        DeliveryMethod.cost_type,
        DeliveryMethod.fixed_cost,
        DeliveryMethod.is_active,
        DeliveryMethod.sort_order,
    ]
    form_columns = [
        DeliveryMethod.name,
        DeliveryMethod.code,
        DeliveryMethod.description,
        DeliveryMethod.cost_type,
        DeliveryMethod.fixed_cost,
        DeliveryMethod.requires_address,
        DeliveryMethod.is_active,
        DeliveryMethod.sort_order,
    ]


class OrderAdmin(ModelView, model=Order):
    name = "Заказ"
    name_plural = "Заказы"
    icon = "fa-solid fa-receipt"
    column_list = [
        Order.id,
        Order.customer_name,
        Order.status,
        Order.payment_status,
        Order.total,
        Order.created_at,
    ]
    column_default_sort = [(Order.id, True)]
    can_create = False  # заказы создаются из магазина, а не вручную в админке
    can_delete = False
    form_columns = [Order.status, Order.tracking_number, Order.cancel_reason]

    async def on_model_change(self, data: dict, model: Order, is_created: bool, request) -> None:
        # Старый статус нужен ДО того, как sqladmin применит data к model —
        # на этом шаге model ещё хранит значения до правки (см.
        # sqladmin._queries._update_sync: on_model_change вызывается раньше
        # _set_attributes_sync). Кладём в request.state, чтобы забрать в
        # after_model_change, когда model уже обновлена и закоммичена.
        request.state.order_old_status = model.status

    async def after_model_change(self, data: dict, model: Order, is_created: bool, request) -> None:
        old_status = getattr(request.state, "order_old_status", None)
        if old_status is None or old_status == model.status:
            return
        changed_by = request.session.get("admin_username") or "admin"
        db = SessionLocal()
        try:
            # Свежий инстанс в своей сессии — `model` пришёл из уже закрытой
            # сессии sqladmin (expire_on_commit=False спасает скалярные
            # колонки, но не ленивую загрузку order.items).
            order = db.get(Order, model.id)
            record_order_status_change(db, order, old_status, order.status, changed_by=changed_by)

            # Остаток списывается только при оплате (см. routers/orders.py:
            # pay_order) — если заказ отменяют из NEW, списания ещё не было,
            # возвращать на склад нечего.
            stock_was_deducted = old_status not in (OrderStatus.NEW, OrderStatus.CANCELLED)
            if order.status == OrderStatus.CANCELLED and stock_was_deducted:
                for item in order.items:
                    product = db.get(Product, item.product_id)
                    if product and product.stock is not None:
                        product.stock += item.quantity
                        db.add(
                            StockMovement(
                                product_id=product.id,
                                delta=item.quantity,
                                reason=StockMovementReason.ORDER_CANCELLED,
                                order_id=order.id,
                                changed_by=changed_by,
                            )
                        )

            db.commit()
        finally:
            db.close()


class OrderItemAdmin(ModelView, model=OrderItem):
    name = "Позиция заказа"
    name_plural = "Позиции заказов"
    icon = "fa-solid fa-list"
    column_list = [OrderItem.order_id, OrderItem.title, OrderItem.price, OrderItem.quantity]
    can_create = False
    can_edit = False
    can_delete = False


class CustomerAdmin(ModelView, model=Customer):
    name = "Клиент"
    name_plural = "Клиенты"
    icon = "fa-solid fa-user"
    column_list = [
        Customer.id,
        Customer.full_name,
        Customer.contact,
        Customer.referral_code,
        Customer.bonus_balance,
        Customer.created_at,
    ]
    column_searchable_list = [Customer.full_name, Customer.contact, Customer.telegram_id]
    can_create = False  # клиенты заводятся автоматически из заказа
    form_columns = [Customer.full_name, Customer.contact, Customer.bonus_balance]


class SubscriptionAdmin(ModelView, model=Subscription):
    name = "Подписка"
    name_plural = "Подписки"
    icon = "fa-solid fa-rotate"
    column_list = [
        Subscription.id,
        Subscription.customer_id,
        Subscription.status,
        Subscription.auto_renew,
        Subscription.current_period_end,
    ]
    form_columns = [
        Subscription.customer,
        Subscription.product,
        Subscription.delivery_method,
        Subscription.delivery_address,
        Subscription.address,
        Subscription.status,
        Subscription.auto_renew,
        Subscription.current_period_end,
        Subscription.cancel_reason,
    ]


class PaymentTransactionAdmin(ModelView, model=PaymentTransaction):
    name = "Транзакция"
    name_plural = "Транзакции"
    icon = "fa-solid fa-money-bill-transfer"
    column_list = [
        PaymentTransaction.id,
        PaymentTransaction.order_id,
        PaymentTransaction.provider,
        PaymentTransaction.amount,
        PaymentTransaction.status,
        PaymentTransaction.created_at,
    ]
    can_create = False
    can_edit = False
    can_delete = False


class BonusTransactionAdmin(ModelView, model=BonusTransaction):
    name = "Бонусная операция"
    name_plural = "Бонусные операции"
    icon = "fa-solid fa-gift"
    column_list = [
        BonusTransaction.id,
        BonusTransaction.customer_id,
        BonusTransaction.amount,
        BonusTransaction.reason,
        BonusTransaction.created_at,
    ]
    can_edit = False
    can_delete = False


class StockMovementAdmin(ModelView, model=StockMovement):
    name = "Движение склада"
    name_plural = "Склад — журнал"
    icon = "fa-solid fa-boxes-stacked"
    column_list = [
        StockMovement.product_id,
        StockMovement.delta,
        StockMovement.reason,
        StockMovement.order_id,
        StockMovement.changed_by,
        StockMovement.created_at,
    ]
    column_default_sort = [(StockMovement.id, True)]
    can_create = False  # пишется только кодом — см. app/admin.py (ProductAdmin/OrderAdmin) и routers/orders.py
    can_edit = False
    can_delete = False


class AddressAdmin(ModelView, model=Address):
    name = "Адрес"
    name_plural = "Адреса"
    icon = "fa-solid fa-location-dot"
    column_list = [Address.id, Address.customer_id, Address.label, Address.is_default, Address.created_at]
    column_searchable_list = [Address.label]
    form_columns = [Address.customer, Address.label, Address.text, Address.is_default]


class OrderStatusHistoryAdmin(ModelView, model=OrderStatusHistory):
    name = "Смена статуса"
    name_plural = "История статусов заказов"
    icon = "fa-solid fa-clock-rotate-left"
    column_list = [
        OrderStatusHistory.order_id,
        OrderStatusHistory.from_status,
        OrderStatusHistory.to_status,
        OrderStatusHistory.changed_by,
        OrderStatusHistory.created_at,
    ]
    column_default_sort = [(OrderStatusHistory.id, True)]
    can_create = False  # пишется только кодом — см. app/order_history.py
    can_edit = False
    can_delete = False


class AdminUserAdmin(ModelView, model=AdminUser):
    """Управление аккаунтами редакторов. Пароль не хранится в форме как
    отдельная колонка (password_hash туда не попадает намеренно) — вместо
    этого виртуальное поле `new_password`, добавленное через scaffold_form:
    пустое при создании — сгенерируется случайный пароль и покажется один
    раз после сохранения (см. Secret.reveal_once); пустое при редактировании
    — пароль не меняется; заполненное — заменяет пароль."""

    name = "Редактор"
    name_plural = "Редакторы"
    icon = "fa-solid fa-user-shield"
    column_list = [
        AdminUser.id,
        AdminUser.username,
        AdminUser.full_name,
        AdminUser.is_active,
        AdminUser.last_login_at,
    ]
    column_searchable_list = [AdminUser.username, AdminUser.full_name]
    form_columns = [AdminUser.username, AdminUser.full_name, AdminUser.is_active]

    async def scaffold_form(self, rules=None):
        form_class = await super().scaffold_form(rules)
        form_class.new_password = wtforms.PasswordField(
            "Новый пароль",
            description="При создании — оставьте пустым, чтобы сгенерировать случайный "
            "и увидеть его один раз после сохранения. При редактировании — оставьте "
            "пустым, чтобы не менять текущий пароль.",
        )
        return form_class

    async def on_model_change(self, data: dict, model: AdminUser, is_created: bool, request) -> None:
        new_password = (data.pop("new_password", "") or "").strip()
        if not new_password and is_created:
            new_password = secrets.token_urlsafe(9)
            request.state.generated_admin_password = new_password
        if new_password:
            data["password_hash"] = hash_password(new_password)

    async def after_model_change(self, data: dict, model: AdminUser, is_created: bool, request) -> None:
        generated = getattr(request.state, "generated_admin_password", None)
        if not generated:
            return
        Secret.reveal_once(
            request,
            value=generated,
            title="Пароль редактора",
            label=f"Логин «{model.username}». Скопируйте пароль сейчас — он больше не будет показан.",
        )


def register_admin(app, engine) -> Admin:
    admin = Admin(app, engine, title="Чтиво · панель редакции", authentication_backend=AdminAuth())
    admin.add_view(ProductAdmin)
    admin.add_view(StockMovementAdmin)
    admin.add_view(DeliveryMethodAdmin)
    admin.add_view(OrderAdmin)
    admin.add_view(OrderItemAdmin)
    admin.add_view(OrderStatusHistoryAdmin)
    admin.add_view(CustomerAdmin)
    admin.add_view(AddressAdmin)
    admin.add_view(SubscriptionAdmin)
    admin.add_view(PaymentTransactionAdmin)
    admin.add_view(BonusTransactionAdmin)
    admin.add_view(AdminUserAdmin)
    return admin
