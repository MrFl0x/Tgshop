import os

from dotenv import load_dotenv

load_dotenv()  # подхватить .env до того, как auth.py и database.py прочитают os.getenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .admin import register_admin
from .database import engine
from .media import MEDIA_ROOT, MEDIA_URL_PREFIX
from .routers import addresses, customers, delivery, orders, products, promo_codes
from .seed import ensure_default_admin, run_seed_if_empty

app = FastAPI(
    title="Чтиво · Магазин API",
    description="Каталог, способы доставки и заказы для Telegram-магазина журнала «Чтиво». "
    "Оплата пока на заглушке — см. app/payments.py.",
)

# Mini App (../miniapp) — отдельный процесс на своём порте/домене (см.
# docs/TZ-02-bot-i-miniapp.md, ТЗ-2 «Технически»), поэтому запросы из браузера
# идут кросс-origin. CORS_ORIGINS в .env — через запятую; по умолчанию, если
# переменная не задана, разрешены только стандартные dev-порты Vite —
# осознанный выбор для локальной разработки, на реальном деплое обязательно
# явно перечислить домен(ы) Mini App.
_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,  # авторизация — через X-Telegram-Init-Data, не через cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# Схему теперь создают/меняют миграции Alembic (`alembic upgrade head`), а не
# create_all при старте — иначе на хостинговой базе (Supabase/Selectel) со
# временем разъедутся два независимых источника правды о структуре таблиц.
# Перед первым запуском на новой базе: alembic upgrade head.
run_seed_if_empty()
ensure_default_admin()

# Отдаёт файлы обложек, загруженные редактором через /admin (см. app/media.py,
# Product.image_upload) — по тому же пути, что сохранён в Product.cover_url.
app.mount(MEDIA_URL_PREFIX, StaticFiles(directory=str(MEDIA_ROOT)), name="media")

app.include_router(products.router)
app.include_router(delivery.router)
app.include_router(orders.router)
app.include_router(addresses.router)
app.include_router(customers.router)
app.include_router(promo_codes.router)

register_admin(app, engine)


@app.get("/", tags=["Служебное"])
def root():
    return {"service": "chtivo-shop-api", "docs": "/docs", "admin": "/admin"}
