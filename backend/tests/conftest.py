"""
Инфраструктура для tests/test_auth_ownership.py.

Требует настоящий Postgres (не SQLite — см. app/database.py) с накатанными
миграциями:

    createdb chtivo_test
    DATABASE_URL=postgresql+psycopg2://<user>@localhost/chtivo_test alembic upgrade head
    DATABASE_URL=postgresql+psycopg2://<user>@localhost/chtivo_test \
        TEST_BOT_TOKEN=test-token pytest

Переменные окружения выставляются здесь, до импорта `app.main` — модули
`app/database.py` и `app/telegram_auth.py` читают DATABASE_URL/BOT_TOKEN
через os.getenv на уровне модуля, при первом импорте, поэтому порядок важен.
BOT_TOKEN намеренно не должен совпадать с реальным токеном бота из .env —
тесты подписывают initData сами (см. `sign_init_data` ниже) и не должны
случайно проходить/падать в зависимости от того, что лежит в .env
разработчика.
"""
import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg2://chtivo:chtivo@127.0.0.1:5432/chtivo_test"
)
TEST_BOT_TOKEN = os.environ.setdefault("BOT_TOKEN", "TEST_BOT_TOKEN_FOR_PYTEST")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

import itertools

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import engine
from app.main import app  # noqa: E402  (импорт после выставления os.environ — см. выше)
from app.seed import run_seed_if_empty

# Каждый тест владения должен работать со своими клиентами — иначе прогоны
# пачкают друг друга в рамках одного pytest-процесса (telegram_id уникален,
# см. app/models.py:Customer). Общий счётчик на процесс, не random — чтобы
# падение теста было воспроизводимо, а не "иногда коллизия".
_telegram_id_seq = itertools.count(900_000_000)

# Таблицы, которые тесты сами наполняют клиентами/заказами — чистятся перед
# прогоном, чтобы повторный запуск pytest на той же test-БД (без пересоздания
# с нуля) не спотыкался о данные из прошлого прогона: счётчик telegram_id
# выше всегда стартует с одного и того же числа, поэтому без очистки второй
# прогон переиспользовал бы telegram_id первого. products/delivery_methods
# тоже сбрасываются и пересеиваются заново — тесты оплаты списывают stock
# (см. routers/orders.py:pay_order), без сброса повторные прогоны на той же
# test-БД со временем увели бы товар в минус. admin_users не трогаем — не
# нужен тестам.
_TABLES_TO_RESET = (
    "bonus_transactions",
    "payment_transactions",
    "stock_movements",
    "order_status_history",
    "order_items",
    "subscriptions",
    "orders",
    "addresses",
    "customers",
    "products",
    "delivery_methods",
)


@pytest.fixture(scope="session", autouse=True)
def _reset_customer_data():
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {', '.join(_TABLES_TO_RESET)} RESTART IDENTITY CASCADE"))
    run_seed_if_empty()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def next_telegram_id():
    def _next() -> int:
        return next(_telegram_id_seq)

    return _next
