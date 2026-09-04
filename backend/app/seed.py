"""
Первичное наполнение пустой БД: все рассматриваемые способы доставки сразу
внесены в таблицу (часть просто выключить/включить в админке, а не
переписывать код) и пара тестовых товаров, чтобы сразу было что заказывать.
"""
from .auth import ADMIN_PASSWORD, ADMIN_USERNAME
from .database import SessionLocal
from .models import AdminUser, DeliveryCostType, DeliveryMethod, Product, ProductType
from .security import hash_password

DEFAULT_DELIVERY_METHODS = [
    dict(
        name="Самовывоз из редакции",
        code="pickup_redaktsiya",
        cost_type=DeliveryCostType.FREE,
        fixed_cost=0,
        requires_address=False,
        sort_order=1,
        description="Бесплатно. Адрес и время забора уточняются после оформления заказа.",
    ),
    dict(
        name="СДЭК — курьером",
        code="cdek_courier",
        cost_type=DeliveryCostType.CALCULATED,
        fixed_cost=300,
        requires_address=True,
        sort_order=2,
        description="Стоимость — заглушка до подключения API СДЭК, сейчас фиксированная.",
    ),
    dict(
        name="СДЭК — до пункта выдачи",
        code="cdek_pvz",
        cost_type=DeliveryCostType.CALCULATED,
        fixed_cost=200,
        requires_address=True,
        sort_order=3,
        description="Стоимость — заглушка до подключения API СДЭК, сейчас фиксированная.",
    ),
    dict(
        name="Boxberry — курьером",
        code="boxberry_courier",
        cost_type=DeliveryCostType.CALCULATED,
        fixed_cost=300,
        requires_address=True,
        sort_order=4,
        description="Стоимость — заглушка до подключения API Boxberry, сейчас фиксированная.",
    ),
    dict(
        name="Boxberry — до пункта выдачи",
        code="boxberry_pvz",
        cost_type=DeliveryCostType.CALCULATED,
        fixed_cost=200,
        requires_address=True,
        sort_order=5,
        description="Стоимость — заглушка до подключения API Boxberry, сейчас фиксированная.",
    ),
    dict(
        name="Почта России",
        code="russian_post",
        cost_type=DeliveryCostType.CALCULATED,
        fixed_cost=250,
        requires_address=True,
        sort_order=6,
        description="Стоимость — заглушка до подключения API Почты России, сейчас фиксированная.",
    ),
    dict(
        name="Свой курьер редакции",
        code="own_courier",
        cost_type=DeliveryCostType.FIXED,
        fixed_cost=400,
        requires_address=True,
        sort_order=7,
        description="Ручная доставка курьером редакции (актуально в пределах Москвы).",
    ),
]

SAMPLE_PRODUCTS = [
    dict(
        title="Чтиво №1 — «Шоу продолжается»",
        type=ProductType.ISSUE,
        description="Первый печатный номер журнала.",
        price=690,
        stock=150,
    ),
    dict(
        title="Подписка на 6 месяцев (4 номера)",
        type=ProductType.SUBSCRIPTION,
        description="Новый номер с доставкой каждые два месяца.",
        price=2400,
        stock=None,
    ),
]


def run_seed_if_empty() -> None:
    db = SessionLocal()
    try:
        if db.query(DeliveryMethod).count() == 0:
            for row in DEFAULT_DELIVERY_METHODS:
                db.add(DeliveryMethod(**row))
        if db.query(Product).count() == 0:
            for row in SAMPLE_PRODUCTS:
                db.add(Product(**row))
        db.commit()
    finally:
        db.close()


def ensure_default_admin() -> None:
    """Создаёт первый аккаунт редактора при пустой таблице admin_users — из
    ADMIN_USERNAME/ADMIN_PASSWORD (.env). Дальше новых редакторов заводить
    через /admin → «Редакторы»; сюда возвращаться не нужно, бутстрап
    одноразовый (срабатывает только пока таблица пуста)."""
    db = SessionLocal()
    try:
        if db.query(AdminUser).count() == 0:
            db.add(
                AdminUser(
                    username=ADMIN_USERNAME,
                    password_hash=hash_password(ADMIN_PASSWORD),
                    full_name="Администратор по умолчанию",
                )
            )
            db.commit()
    finally:
        db.close()
