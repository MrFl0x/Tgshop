"""
Логин для /admin. Раньше сверялся напрямую с ADMIN_USERNAME/ADMIN_PASSWORD
из .env — один общий логин на всю редакцию. Теперь — таблица `AdminUser`:
у каждого редактора свой логин, и видно, кто именно менял статус заказа
(OrderStatusHistory.changed_by). ADMIN_USERNAME/ADMIN_PASSWORD в .env теперь
используются только для бутстрапа первой записи при пустой таблице (см.
app/seed.py:ensure_default_admin) — новых редакторов заводить через саму
панель, вкладка «Редакторы».
"""
import os
from datetime import datetime

from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
from starlette.requests import Request

from .database import SessionLocal
from .models import AdminUser
from .security import verify_password

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "chtivo-admin")
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "dev-insecure-secret-change-me-in-.env")


class AdminAuth(AuthenticationBackend):
    def __init__(self) -> None:
        super().__init__(secret_key=ADMIN_SECRET_KEY)

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form.get("username"), form.get("password")
        if not username or not password:
            return False

        db = SessionLocal()
        try:
            user = db.scalar(select(AdminUser).where(AdminUser.username == username))
            if not user or not user.is_active or not verify_password(password, user.password_hash):
                return False
            user.last_login_at = datetime.utcnow()
            db.commit()
        finally:
            db.close()

        request.session.update({"admin_authenticated": "1", "admin_username": username})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        if request.session.get("admin_authenticated") != "1":
            return False
        username = request.session.get("admin_username")
        if not username:
            return False

        # Перепроверяем по базе на каждый запрос (не только при логине) —
        # чтобы деактивированный редактор (AdminUser.is_active=False) сразу
        # терял доступ, а не только со следующего входа.
        db = SessionLocal()
        try:
            user = db.scalar(select(AdminUser).where(AdminUser.username == username))
            return bool(user and user.is_active)
        finally:
            db.close()
