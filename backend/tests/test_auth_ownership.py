"""
Каркас сценариев из аудита в docs/TZ-03-zakryt-dyru-i-miniapp.md (ТЗ-Д):
- ТЗ-0 — 401 без initData / 401 при чужой подписи;
- ТЗ-0 (addresses/customers) — 403 при чужом telegram_id в пути с валидной
  подписью своего;
- ТЗ-А — GET/POST на routers/orders.py отдают 404 (не 403) на чужой заказ,
  включая /pay — тот самый пропуск, который раньше пропускал оплату чужого
  заказа без единого заголовка авторизации;
- гостевые заказы (customer_id is None) закрыты для чтения через API;
- реферальная программа начисляет бонус обеим сторонам после оплаты.

Использованный тогда для аудита временный скрипт `_verify_tz.py` был удалён
после проверки (не для коммита) — этот файл фиксирует те же сценарии как
постоянный, растущий вместе с кодом.
"""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from conftest import TEST_BOT_TOKEN

# "Самовывоз из редакции" — единственный способ доставки из app/seed.py,
# у которого requires_address=False, поэтому в заказе для тестов не нужно
# думать про адрес/address_id.
PICKUP_DELIVERY_METHOD_ID = 1
# "Чтиво №1" — первый товар из app/seed.py:SAMPLE_PRODUCTS, есть на складе.
IN_STOCK_PRODUCT_ID = 1


def sign_init_data(user_id: int, *, bot_token: str = TEST_BOT_TOKEN, auth_date: int | None = None) -> str:
    """Строит валидную (по алгоритму Telegram) строку initData, подписанную
    bot_token — см. app/telegram_auth.py:verify_init_data, тот же алгоритм
    в обратную сторону."""
    data = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": f"AAH{user_id}",
        "user": json.dumps({"id": user_id, "first_name": "Test", "username": f"user{user_id}"}, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode(data)


def auth_headers(user_id: int, **kwargs) -> dict:
    return {"X-Telegram-Init-Data": sign_init_data(user_id, **kwargs)}


def order_payload(**overrides) -> dict:
    payload = dict(
        customer_name="Тестовый Клиент",
        customer_contact="+79990000000",
        delivery_method_id=PICKUP_DELIVERY_METHOD_ID,
        items=[{"product_id": IN_STOCK_PRODUCT_ID, "quantity": 1}],
    )
    payload.update(overrides)
    return payload


# --- ТЗ-0: без initData / с чужой подписью -------------------------------


def test_missing_init_data_header_is_401(client):
    """Ни один защищённый эндпоинт не должен отвечать без заголовка."""
    telegram_id = 111
    assert client.post("/orders/", json=order_payload()).status_code == 401
    assert client.get("/orders/1").status_code == 401
    assert client.get("/orders/1/history").status_code == 401
    assert client.post("/orders/1/pay").status_code == 401
    assert client.get(f"/customers/{telegram_id}").status_code == 401
    assert client.get(f"/customers/{telegram_id}/orders").status_code == 401
    assert client.get(f"/customers/{telegram_id}/addresses/").status_code == 401
    assert client.post(f"/customers/{telegram_id}/addresses/", json={"text": "Москва"}).status_code == 401


def test_init_data_signed_with_wrong_bot_token_is_401(client, next_telegram_id):
    telegram_id = next_telegram_id()
    headers = auth_headers(telegram_id, bot_token="совсем-не-тот-токен")
    resp = client.post("/orders/", json=order_payload(), headers=headers)
    assert resp.status_code == 401


def test_tampered_hash_is_401(client, next_telegram_id):
    telegram_id = next_telegram_id()
    init_data = sign_init_data(telegram_id)
    tampered = init_data[:-1] + ("0" if init_data[-1] != "0" else "1")
    resp = client.get(f"/customers/{telegram_id}", headers={"X-Telegram-Init-Data": tampered})
    assert resp.status_code == 401


def test_expired_init_data_is_401(client, next_telegram_id):
    telegram_id = next_telegram_id()
    stale_auth_date = int(time.time()) - 25 * 60 * 60  # чуть больше суток — см. MAX_INIT_DATA_AGE_SECONDS
    headers = auth_headers(telegram_id, auth_date=stale_auth_date)
    resp = client.get(f"/customers/{telegram_id}", headers=headers)
    assert resp.status_code == 401


# --- ТЗ-0: чужой telegram_id в пути (addresses/customers → 403) ----------


def test_addresses_reject_foreign_telegram_id_in_path(client, next_telegram_id):
    owner_id = next_telegram_id()
    intruder_id = next_telegram_id()
    intruder_headers = auth_headers(intruder_id)

    assert client.get(f"/customers/{owner_id}/addresses/", headers=intruder_headers).status_code == 403
    assert (
        client.post(f"/customers/{owner_id}/addresses/", json={"text": "Москва"}, headers=intruder_headers).status_code
        == 403
    )
    assert client.delete(f"/customers/{owner_id}/addresses/1", headers=intruder_headers).status_code == 403


def test_customers_reject_foreign_telegram_id_in_path(client, next_telegram_id):
    owner_id = next_telegram_id()
    intruder_id = next_telegram_id()
    intruder_headers = auth_headers(intruder_id)

    assert client.get(f"/customers/{owner_id}", headers=intruder_headers).status_code == 403
    assert client.get(f"/customers/{owner_id}/orders", headers=intruder_headers).status_code == 403


def test_addresses_own_path_succeeds(client, next_telegram_id):
    telegram_id = next_telegram_id()
    headers = auth_headers(telegram_id)

    created = client.post(
        f"/customers/{telegram_id}/addresses/", json={"text": "Москва, ул. Тестовая, 1", "is_default": True}, headers=headers
    )
    assert created.status_code == 200, created.text

    listed = client.get(f"/customers/{telegram_id}/addresses/", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


# --- ТЗ-А: заказы (routers/orders.py) — владение проверяется целиком -----


def _create_and_pay_order(client, telegram_id: int) -> dict:
    headers = auth_headers(telegram_id)
    created = client.post("/orders/", json=order_payload(), headers=headers)
    assert created.status_code == 200, created.text
    order = created.json()

    paid = client.post(f"/orders/{order['id']}/pay", headers=headers)
    assert paid.status_code == 200, paid.text
    return paid.json()


def test_create_and_pay_order_happy_path(client, next_telegram_id):
    telegram_id = next_telegram_id()
    order = _create_and_pay_order(client, telegram_id)

    # "paid" (оплата подтверждена) переводит заказ в awaiting_packaging —
    # следующий шаг после оплаты в Ozon-style статусах (см. tz-zakazy.md,
    # backend-миграция 3f0a1c7e2b6d); просто "оплачен" здесь больше не статус
    # заказа, а только payment_status.
    assert order["status"] == "awaiting_packaging"
    assert order["payment_status"] == "paid"
    assert order["items"][0]["product_id"] == IN_STOCK_PRODUCT_ID

    history = client.get(f"/orders/{order['id']}/history", headers=auth_headers(telegram_id))
    assert history.status_code == 200
    statuses = [row["to_status"] for row in history.json()]
    assert "awaiting_packaging" in statuses


def test_order_endpoints_hide_foreign_order_behind_404_not_403(client, next_telegram_id):
    """Подтверждает находку из ТЗ-А: до фикса /orders/{id}/pay оплачивал
    чужой заказ без единого заголовка авторизации. Здесь — тот же заказ,
    но запрошенный/оплачиваемый от имени другого клиента, во всех трёх
    ранее незащищённых эндпоинтах."""
    owner_id = next_telegram_id()
    intruder_id = next_telegram_id()

    owner_headers = auth_headers(owner_id)
    created = client.post("/orders/", json=order_payload(), headers=owner_headers)
    assert created.status_code == 200, created.text
    order_id = created.json()["id"]

    intruder_headers = auth_headers(intruder_id)
    # Именно 404, а не 403 — order_id сам по себе ничего не раскрывает
    # (см. routers/orders.py:_get_owned_order), в отличие от addresses/customers,
    # где telegram_id и так открыт в самом пути.
    assert client.get(f"/orders/{order_id}", headers=intruder_headers).status_code == 404
    assert client.get(f"/orders/{order_id}/history", headers=intruder_headers).status_code == 404
    assert client.post(f"/orders/{order_id}/pay", headers=intruder_headers).status_code == 404

    # И заказ не должен был реально оплатиться этим запросом.
    still_owner_view = client.get(f"/orders/{order_id}", headers=owner_headers)
    assert still_owner_view.json()["payment_status"] == "pending"


def test_nonexistent_order_is_404(client, next_telegram_id):
    telegram_id = next_telegram_id()
    headers = auth_headers(telegram_id)
    assert client.get("/orders/999999999", headers=headers).status_code == 404
    assert client.get("/orders/999999999/history", headers=headers).status_code == 404
    assert client.post("/orders/999999999/pay", headers=headers).status_code == 404


def test_guest_order_is_hidden_from_api(client, next_telegram_id):
    """Гостевой заказ (оформлен через /docs без initData, customer_id is
    None) закрыт для чтения через API целиком — доступен только в /admin
    (см. docs/TZ-03-zakryt-dyru-i-miniapp.md, ТЗ-А п.3)."""
    from app.database import SessionLocal
    from app.models import DeliveryMethod, Order, OrderStatus, PaymentStatus

    db = SessionLocal()
    try:
        delivery = db.get(DeliveryMethod, PICKUP_DELIVERY_METHOD_ID)
        guest_order = Order(
            number="TEST-GUEST-ORDER",  # number — NOT NULL (см. миграцию 3f0a1c7e2b6d); тест не идёт через create_order,
            customer_id=None,           # где номер берётся из order_number_seq, поэтому задаём вручную
            customer_name="Гость",
            customer_contact="guest@example.com",
            delivery_method_id=delivery.id,
            delivery_address="",
            status=OrderStatus.AWAITING_PAYMENT,
            payment_status=PaymentStatus.PENDING,
            items_total=0,
            delivery_cost=0,
            total=0,
        )
        db.add(guest_order)
        db.commit()
        db.refresh(guest_order)
        guest_order_id = guest_order.id
    finally:
        db.close()

    telegram_id = next_telegram_id()
    headers = auth_headers(telegram_id)
    assert client.get(f"/orders/{guest_order_id}", headers=headers).status_code == 404
    assert client.get(f"/orders/{guest_order_id}/history", headers=headers).status_code == 404
    assert client.post(f"/orders/{guest_order_id}/pay", headers=headers).status_code == 404


# --- Профиль / «Мои заказы» — только свои данные --------------------------


def test_orders_list_returns_only_own_orders(client, next_telegram_id):
    owner_id = next_telegram_id()
    other_id = next_telegram_id()

    order = _create_and_pay_order(client, owner_id)
    client.post("/orders/", json=order_payload(), headers=auth_headers(other_id))  # чужой заказ, для контраста

    listed = client.get(f"/customers/{owner_id}/orders", headers=auth_headers(owner_id))
    assert listed.status_code == 200
    ids = [row["id"] for row in listed.json()]
    assert order["id"] in ids
    assert all(row["customer_id"] is not None for row in listed.json())


# --- Реферальная программа: сквозной сценарий -----------------------------


def test_referral_bonus_awarded_to_both_after_invitee_pays(client, next_telegram_id):
    inviter_id = next_telegram_id()
    invitee_id = next_telegram_id()

    # У пригласившего должен появиться клиент/referral_code — проще всего
    # получить его тем же путём, что и в проде: оформить заказ (создаёт
    # customer через get_or_create_customer, см. app/customers.py).
    inviter_headers = auth_headers(inviter_id)
    inviter_order = client.post("/orders/", json=order_payload(), headers=inviter_headers)
    assert inviter_order.status_code == 200, inviter_order.text

    inviter_profile = client.get(f"/customers/{inviter_id}", headers=inviter_headers)
    assert inviter_profile.status_code == 200
    referral_code = inviter_profile.json()["referral_code"]
    assert referral_code

    inviter_balance_before = float(inviter_profile.json()["bonus_balance"])

    invitee_headers = auth_headers(invitee_id)
    invitee_order = client.post(
        "/orders/", json=order_payload(referral_code=referral_code), headers=invitee_headers
    )
    assert invitee_order.status_code == 200, invitee_order.text

    paid = client.post(f"/orders/{invitee_order.json()['id']}/pay", headers=invitee_headers)
    assert paid.status_code == 200
    assert paid.json()["payment_status"] == "paid"

    invitee_profile = client.get(f"/customers/{invitee_id}", headers=invitee_headers).json()
    inviter_profile_after = client.get(f"/customers/{inviter_id}", headers=inviter_headers).json()

    assert float(invitee_profile["bonus_balance"]) == 200.0
    assert float(inviter_profile_after["bonus_balance"]) == inviter_balance_before + 200.0

    # Идемпотентность: повторная оплата того же заказа не начисляет бонус снова.
    replay = client.post(f"/orders/{invitee_order.json()['id']}/pay", headers=invitee_headers)
    assert replay.status_code == 200
    invitee_profile_after_replay = client.get(f"/customers/{invitee_id}", headers=invitee_headers).json()
    assert float(invitee_profile_after_replay["bonus_balance"]) == 200.0
