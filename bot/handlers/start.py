"""
/start и приветственный экран. Deep-link с реферальным кодом
(`t.me/<bot>?start=CHT00001`) — см. docs/TZ-02-bot-i-miniapp.md, ТЗ-1: код
запоминаем только при первом визите с ним, дальше он живёт до открытия
Mini App (referrals.py). Повторный /start без кода просто показывает тот же
экран — если код уже был запомнен раньше в этой же сессии бота, кнопка
Mini App всё ещё унесёт его с собой.
"""
import re

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from ..keyboards import main_menu_keyboard
from ..referrals import get_referral, remember_referral
from ..texts import GREETING

router = Router(name="start")

# Формат реферального кода — app/customers.py:_make_referral_code в backend
# ("CHT" + id клиента, дополненный нулями до 5 знаков).
REFERRAL_CODE_RE = re.compile(r"^CHT\d{5}$")


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    user_id = message.from_user.id
    payload = (command.args or "").strip()

    if payload and REFERRAL_CODE_RE.match(payload):
        remember_referral(user_id, payload)

    await message.answer(
        GREETING,
        reply_markup=main_menu_keyboard(get_referral(user_id)),
    )
