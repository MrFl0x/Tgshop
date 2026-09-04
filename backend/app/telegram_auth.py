"""
Проверка подписи `initData`, которую Telegram Mini App кладёт в заголовок
`X-Telegram-Init-Data` на каждый запрос к backend. До этого модуля
`telegram_id` приходил как обычный параметр запроса/пути — представиться
можно было кем угодно и увидеть чужие адреса/заказы/бонусы (см.
docs/TZ-02-bot-i-miniapp.md, ТЗ-0). Теперь для операций, завязанных на
личность клиента, telegram_id берётся только из проверенного initData.

Алгоритм проверки — ровно тот, что описан в доке Telegram:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Telegram переиздаёт initData при каждом открытии Mini App, так что валидная
# строка всегда свежая. Большой возраст обычно значит, что строка утекла и
# переиспользуется откуда-то ещё (лог, ссылка, кэш) — 24 часа с запасом.
MAX_INIT_DATA_AGE_SECONDS = 24 * 60 * 60


class InvalidInitData(Exception):
    """initData отсутствует, подделана, просрочена или сервер не настроен."""


def verify_init_data(init_data: str, bot_token: str) -> dict:
    """Проверяет подпись `init_data` и возвращает разобранные поля (включая
    распарсенный `user`, если он был). Бросает InvalidInitData на любую
    проблему — вызывающая сторона решает, что с этим делать (обычно 401)."""
    if not init_data:
        raise InvalidInitData("initData пуст")
    if not bot_token:
        # Fail closed: без BOT_TOKEN в .env сервер не может проверить подпись
        # никого — лучше 401 всем, чем молча доверять непроверенным данным.
        raise InvalidInitData("BOT_TOKEN не настроен на сервере")

    try:
        pairs = parse_qsl(init_data, strict_parsing=True, keep_blank_values=True)
    except ValueError as exc:
        raise InvalidInitData("initData не парсится как query-строка") from exc
    data = dict(pairs)

    received_hash = data.pop("hash", None)
    if not received_hash:
        raise InvalidInitData("отсутствует поле hash")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise InvalidInitData("подпись не совпадает")

    auth_date = data.get("auth_date")
    if auth_date:
        try:
            age_seconds = time.time() - int(auth_date)
        except ValueError as exc:
            raise InvalidInitData("некорректный auth_date") from exc
        if age_seconds > MAX_INIT_DATA_AGE_SECONDS:
            raise InvalidInitData("initData просрочен")

    if "user" in data:
        try:
            data["user"] = json.loads(data["user"])
        except (json.JSONDecodeError, TypeError) as exc:
            raise InvalidInitData("некорректное поле user") from exc

    return data


def get_verified_telegram_id(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
) -> str:
    """FastAPI-зависимость: проверяет initData из заголовка запроса и
    возвращает telegram_id того, кто реально его прислал (а не того, кем он
    назвался в теле/пути). 401, если заголовка нет, подпись не сошлась,
    initData просрочен или в нём нет user.id."""
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Не хватает заголовка X-Telegram-Init-Data")

    try:
        data = verify_init_data(x_telegram_init_data, BOT_TOKEN)
    except InvalidInitData as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user = data.get("user") or {}
    telegram_id = user.get("id")
    if telegram_id is None:
        raise HTTPException(status_code=401, detail="initData без user.id")
    return str(telegram_id)
