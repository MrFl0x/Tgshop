"""Клавиатуры бота."""
from urllib.parse import urlencode

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from .config import MINIAPP_URL


def main_menu_keyboard(referral_code: str | None = None) -> InlineKeyboardMarkup:
    """Кнопка открытия Mini App. Если для этого пользователя есть непогашенный
    реферальный код (см. referrals.py) — прокидываем его в URL параметром
    `startapp`, чтобы Mini App могла подставить его как referral_code в
    первый заказ (см. docs/TZ-02-bot-i-miniapp.md, ТЗ-1)."""
    url = MINIAPP_URL
    if referral_code:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode({'startapp': referral_code})}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛍 Открыть магазин", web_app=WebAppInfo(url=url))],
        ]
    )
