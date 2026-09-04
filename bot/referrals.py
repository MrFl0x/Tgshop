"""
Реферальный код из deep-link (`/start CHT00001`) — держим в памяти процесса
на время сессии пользователя, до того как он откроет Mini App: код
прокидывается в её URL параметром `startapp` (см. keyboards.py), дальше это
уже ответственность Mini App/backend передать его как `referral_code` в
`POST /orders/` (app/customers.py:get_or_create_customer в backend).

Не персистентно и не на телеграм-юзера навсегда: рестарт бота сбрасывает
состояние, повторный переход по реферальной ссылке восстановит его — для
MVP-объёма этого достаточно (см. docs/TZ-02-bot-i-miniapp.md, ТЗ-1).
TODO: если станет проблемой — перенести в файл/Redis вместо dict в памяти.
"""

_pending: dict[int, str] = {}


def remember_referral(user_id: int, referral_code: str) -> None:
    _pending[user_id] = referral_code


def get_referral(user_id: int) -> str | None:
    return _pending.get(user_id)
