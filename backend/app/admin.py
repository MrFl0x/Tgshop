"""
Веб-админка редакции на SQLAdmin: добавление/редактирование товаров и
способов доставки без единой строчки кода, плюс панель заказов со статусами
и трек-номером — та же сущность, что описана в продуктовом плане.
"""
import secrets
from datetime import datetime, timedelta

import wtforms
from sqladmin import Admin, BaseView, ModelView, expose
from sqladmin.i18n import I18nConfig
from sqladmin.secret import Secret
from starlette.requests import Request
from starlette.responses import Response

from . import analytics
from .admin_orders import OrdersPanelView
from .auth import AdminAuth
from .database import SessionLocal
from .media import image_public_url
from sqladmin.editors import JSONEditorField

from .models import (
    Address,
    AdminUser,
    BonusTransaction,
    Customer,
    DeliveryMethod,
    DiscountType,
    PaymentTransaction,
    Product,
    ProductPhoto,
    ProductType,
    PromoCode,
    StockMovement,
    StockMovementReason,
    Subscription,
)
from .security import hash_password


PRODUCT_TYPE_LABELS_RU = {
    ProductType.ISSUE: "Номер журнала",
    ProductType.SUBSCRIPTION: "Подписка",
    ProductType.MERCH: "Мерч",
}


def _format_product_type(model: Product, attribute) -> str:
    return PRODUCT_TYPE_LABELS_RU.get(model.type, model.type.value if model.type else "—")


class ProductAdmin(ModelView, model=Product):
    name = "Товар"
    name_plural = "Товары"
    icon = "fa-solid fa-book"
    column_list = [Product.id, Product.title, Product.type, Product.price, Product.stock, Product.is_active]
    column_searchable_list = [Product.title]
    column_sortable_list = [Product.id, Product.price, Product.stock]
    # i18n_config (см. register_admin) переводит только чужие надписи самого
    # sqladmin (Export/Actions/Search и т.п.) — названия наших полей и
    # значения enum'ов (ISSUE/SUBSCRIPTION/...) он не трогает, это делаем
    # руками через column_labels/column_formatters/form_args ниже — как в
    # Ozon, редактор нигде не должен видеть английские системные имена.
    column_labels = {
        Product.id: "ID",
        Product.title: "Название",
        Product.type: "Тип",
        Product.description: "Описание",
        Product.image_upload: "Фото (загрузить)",
        Product.cover_url: "Ссылка на обложку",
        Product.characteristics: "Характеристики",
        Product.price: "Цена",
        Product.stock: "Остаток",
        Product.is_active: "Активен",
        Product.created_at: "Создан",
        Product.updated_at: "Изменён",
    }
    column_formatters = {Product.type: _format_product_type}
    column_formatters_detail = {Product.type: _format_product_type}
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
        Product.characteristics,
        Product.price,
        Product.stock,
        Product.is_active,
    ]
    # image_upload/cover_url — главное фото карточки (как обложка на Ozon),
    # дополнительные фото галереи — отдельный раздел "Фото товара"
    # (ProductPhotoAdmin ниже), сначала нужно сохранить товар, чтобы у него
    # появился id, на который они ссылаются.
    # "type" тоже переопределён на голый SelectField: у enum-колонок sqladmin
    # безусловно перезаписывает kwargs["choices"] в conv_enum (см.
    # sqladmin/forms.py) — form_args={"choices": [...]} для Enum-полей молча
    # игнорируется тем же способом, что сработал для JSONEditorField ниже, но
    # с готовым field-классом заново. coerce=str — значения choices уже те же
    # строки-имена enum'а (ISSUE/SUBSCRIPTION/MERCH), что sqladmin ожидает при
    # записи обратно в модель, просто с человеческой подписью рядом.
    form_overrides = {"characteristics": JSONEditorField, "type": wtforms.SelectField}
    form_args = {
        "image_upload": {"description": "Загрузите файл — публичная ссылка сама подставится в поле «Ссылка на обложку» ниже. Это главное фото карточки — доп. фото добавляются в разделе «Фото товара» после сохранения."},
        "cover_url": {"description": "Заполняется автоматически при загрузке файла выше; можно вписать и внешнюю ссылку на картинку вручную."},
        "characteristics": {
            "mode": "form",
            "description": "Характеристики карточки — как на Ozon: название и значение, например «Автор» / «Год» / «Страниц». Пустой список ({}) — характеристик нет.",
        },
        "type": {"choices": [(t.name, PRODUCT_TYPE_LABELS_RU[t]) for t in ProductType], "coerce": str},
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


class ProductPhotoAdmin(ModelView, model=ProductPhoto):
    """Галерея доп. фото товара (как на Ozon — несколько снимков карточки).
    Главное фото остаётся полем на самом товаре (Product.image_upload) —
    sqladmin не умеет редактировать несколько файлов в одном поле формы,
    поэтому доп. фото заводятся здесь отдельными записями со ссылкой на
    товар; sort_order задаёт порядок показа."""

    name = "Фото товара"
    name_plural = "Фото товаров"
    icon = "fa-solid fa-images"
    column_list = [ProductPhoto.id, ProductPhoto.product, ProductPhoto.image_upload, ProductPhoto.sort_order]
    column_default_sort = [(ProductPhoto.product_id, False), (ProductPhoto.sort_order, False)]
    column_labels = {
        ProductPhoto.id: "ID",
        ProductPhoto.product: "Товар",
        ProductPhoto.image_upload: "Фото",
        ProductPhoto.sort_order: "Порядок",
    }
    form_columns = [ProductPhoto.product, ProductPhoto.image_upload, ProductPhoto.sort_order]
    form_args = {
        "sort_order": {"description": "Порядок в галерее — чем меньше число, тем раньше фото показывается после главного."},
    }


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


DISCOUNT_TYPE_LABELS_RU = {
    DiscountType.PERCENT: "Процент",
    DiscountType.FIXED: "Фиксированная сумма",
}


def _format_discount_type(model: PromoCode, attribute) -> str:
    return DISCOUNT_TYPE_LABELS_RU.get(model.discount_type, model.discount_type.value if model.discount_type else "—")


class PromoCodeAdmin(ModelView, model=PromoCode):
    """Промокоды на скидку — применяются в Mini App при оформлении заказа
    (app/promotions.py, routers/orders.py:create_order). code хранится и
    сравнивается регистронезависимо (см. routers/promo_codes.py) — редактор
    может вводить как угодно."""

    name = "Промокод"
    name_plural = "Промокоды"
    icon = "fa-solid fa-tags"
    column_list = [
        PromoCode.code,
        PromoCode.discount_type,
        PromoCode.discount_value,
        PromoCode.is_active,
        PromoCode.valid_until,
    ]
    column_searchable_list = [PromoCode.code]
    column_labels = {
        PromoCode.code: "Код",
        PromoCode.discount_type: "Тип скидки",
        PromoCode.discount_value: "Размер скидки",
        PromoCode.is_active: "Активен",
        PromoCode.valid_until: "Действует до",
    }
    column_formatters = {PromoCode.discount_type: _format_discount_type}
    column_formatters_detail = {PromoCode.discount_type: _format_discount_type}
    form_columns = [
        PromoCode.code,
        PromoCode.discount_type,
        PromoCode.discount_value,
        PromoCode.is_active,
        PromoCode.valid_until,
    ]
    # discount_type — тот же приём, что и Product.type выше: голый SelectField
    # вместо enum-конвертера sqladmin, иначе form_args["choices"] молча
    # перезаписывается обратно на PERCENT/FIXED.
    form_overrides = {"discount_type": wtforms.SelectField}
    form_args = {
        "discount_value": {"description": "Смотря по типу скидки выше — процент (0-100) либо сумма в ₽."},
        "valid_until": {"description": "Пусто — бессрочный."},
        "discount_type": {"choices": [(t.name, DISCOUNT_TYPE_LABELS_RU[t]) for t in DiscountType], "coerce": str},
    }

    async def on_model_change(self, data: dict, model: PromoCode, is_created: bool, request) -> None:
        code = (data.get("code") or "").strip().upper()
        if code:
            data["code"] = code


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


class RevenueReportView(BaseView):
    """Отчёт по выручке (app/analytics.py) — считается на лету поверх
    Order/OrderItem по фильтрам из query-параметров, отдельного экрана
    "выгрузки" нет: печать/сохранение страницы браузером достаточно для
    маленькой редакции."""

    name = "Отчёт по выручке"
    identity = "reports-revenue"
    icon = "fa-solid fa-chart-line"

    @expose("/reports/revenue", methods=["GET"])
    async def revenue_report(self, request: Request) -> Response:
        today = datetime.utcnow().date()
        date_from_str = request.query_params.get("from") or today.replace(day=1).isoformat()
        date_to_str = request.query_params.get("to") or today.isoformat()
        group_by = request.query_params.get("group_by") or "day"
        if group_by not in ("day", "month"):
            group_by = "day"

        try:
            date_from = datetime.strptime(date_from_str, "%Y-%m-%d")
            # Верхняя граница исключительная — начало следующего дня после "по",
            # чтобы сам день "по" вошёл в период целиком.
            date_to_exclusive = datetime.strptime(date_to_str, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            date_from_str = today.replace(day=1).isoformat()
            date_to_str = today.isoformat()
            date_from = datetime.strptime(date_from_str, "%Y-%m-%d")
            date_to_exclusive = datetime.strptime(date_to_str, "%Y-%m-%d") + timedelta(days=1)

        db = SessionLocal()
        try:
            summary = analytics.revenue_summary(db, date_from, date_to_exclusive)
            points = analytics.revenue_by_period(db, date_from, date_to_exclusive, group_by)
            products = analytics.revenue_by_product(db, date_from, date_to_exclusive)
        finally:
            db.close()

        return await self.templates.TemplateResponse(
            request,
            "reports/revenue.html",
            {
                "date_from": date_from_str,
                "date_to": date_to_str,
                "group_by": group_by,
                "summary": summary,
                "points": points,
                "products": products,
            },
        )


def register_admin(app, engine) -> Admin:
    # Идёт полный редизайн панели — разделы включаются обратно по одному,
    # по мере переделки, а не все разом. Чтобы вернуть раздел — раскомментировать
    # соответствующую строку ниже (сам класс *Admin выше не трогали).
    admin = Admin(
        app,
        engine,
        title="Чтиво · панель редакции",
        authentication_backend=AdminAuth(),
        # Разделы, ещё не переписанные под свою вёрстку (Товары, Фото
        # товаров, Промокоды — ср. «Заказы» в app/admin_orders.py, у которых
        # свой шаблон), рисует голый sqladmin: без i18n_config все его
        # надписи (Export/Actions/Search/Showing X of Y/prev/next и т.п.)
        # остаются на английском вперемешку с русскими названиями сущностей.
        # Встроенный в sqladmin каталог переводов покрывает это готовым
        # переводом chrome-строк — нужен только пакет babel (requirements.txt).
        i18n_config=I18nConfig(default_locale="ru"),
    )
    # admin.add_view(RevenueReportView)
    admin.add_view(ProductAdmin)
    admin.add_view(ProductPhotoAdmin)
    admin.add_view(OrdersPanelView)  # «Заказы» — свой BaseView, см. app/admin_orders.py
    admin.add_view(PromoCodeAdmin)
    # admin.add_view(StockMovementAdmin)
    # admin.add_view(DeliveryMethodAdmin)
    # admin.add_view(CustomerAdmin)
    # admin.add_view(AddressAdmin)
    # admin.add_view(SubscriptionAdmin)
    # admin.add_view(PaymentTransactionAdmin)
    # admin.add_view(BonusTransactionAdmin)
    # admin.add_view(AdminUserAdmin)
    return admin
