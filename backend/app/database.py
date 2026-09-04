"""
Подключение к БД. Фолбэк без DATABASE_URL в .env — локальный SQLite-файл.
Меняется на PostgreSQL простой сменой DATABASE_URL в .env — код моделей и
роутеров трогать не нужно.

Важно: SQLite-фолбэк годится только для самой первой миграции (создание
схемы с нуля). Начиная с миграции `04687c619c59_...` используется
`op.create_foreign_key` напрямую, а SQLite не поддерживает `ALTER TABLE ADD
CONSTRAINT` без batch-режима Alembic — `alembic upgrade head` на свежей
SQLite падает с `NotImplementedError`. Для разработки нужен Postgres
(см. README.md — быстрый старт на Supabase). Чинить batch-режим ради пути,
которым уже никто не пользуется, смысла нет — см.
docs/TZ-03-zakryt-dyru-i-miniapp.md, ТЗ-Б.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chtivo_shop.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# pool_pre_ping — обязателен для хостингового Postgres (Supabase/Selectel):
# такие соединения периодически рвутся по простою, пинг перед каждым
# запросом сам переоткрывает соединение вместо падения запроса с ошибкой.
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
