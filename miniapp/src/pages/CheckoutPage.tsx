import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Address, DeliveryMethod } from "../api/types";
import { PageHeader } from "../components/PageHeader";
import { ErrorBanner, Loading } from "../components/Loading";
import { useCart } from "../state/CartContext";
import { formatPrice } from "../format";
import { getCurrentUserId, getStartParam, getWebApp, hapticError, hapticSuccess } from "../telegram";

const NEW_ADDRESS = "__new__";

export function CheckoutPage() {
  const { lines, totalPrice, clear } = useCart();
  const navigate = useNavigate();
  const telegramId = getCurrentUserId();
  const tgUser = getWebApp()?.initDataUnsafe.user;

  const [methods, setMethods] = useState<DeliveryMethod[] | null>(null);
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [customerName, setCustomerName] = useState(
    [tgUser?.first_name, tgUser?.last_name].filter(Boolean).join(" "),
  );
  const [customerContact, setCustomerContact] = useState(tgUser?.username ? `@${tgUser.username}` : "");
  const [deliveryMethodId, setDeliveryMethodId] = useState<number | null>(null);
  const [addressChoice, setAddressChoice] = useState<string>(NEW_ADDRESS);
  const [newAddressText, setNewAddressText] = useState("");
  const [saveNewAddress, setSaveNewAddress] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api.deliveryMethods.list(),
      telegramId ? api.addresses.list(telegramId).catch(() => []) : Promise.resolve([]),
    ])
      .then(([methodsRes, addressesRes]) => {
        if (cancelled) return;
        setMethods(methodsRes);
        setAddresses(addressesRes);
        if (methodsRes.length > 0) setDeliveryMethodId(methodsRes[0].id);
        const defaultAddr = addressesRes.find((a) => a.is_default);
        if (defaultAddr) setAddressChoice(String(defaultAddr.id));
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err instanceof ApiError ? String(err.message) : "Не удалось загрузить способы доставки.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [telegramId]);

  const selectedMethod = useMemo(() => methods?.find((m) => m.id === deliveryMethodId) ?? null, [methods, deliveryMethodId]);
  const needsAddress = selectedMethod?.requires_address ?? false;
  const deliveryCost = selectedMethod ? Number(selectedMethod.fixed_cost ?? 0) : 0;
  const grandTotal = totalPrice + (selectedMethod?.cost_type === "free" ? 0 : deliveryCost);

  if (lines.length === 0) {
    navigate("/cart", { replace: true });
    return null;
  }

  const canSubmit =
    !submitting &&
    customerName.trim() &&
    customerContact.trim() &&
    deliveryMethodId !== null &&
    (!needsAddress || (addressChoice !== NEW_ADDRESS ? true : newAddressText.trim().length > 0));

  async function handleSubmit() {
    if (!canSubmit || !deliveryMethodId) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const usingSavedAddress = needsAddress && addressChoice !== NEW_ADDRESS;
      const order = await api.orders.create({
        // Реферальный код — из startapp-параметра deep-link'а бота (см.
        // bot/README.md и bot/keyboards.py). Backend сам решает, применим ли
        // он (уже есть у клиента — код игнорируется, см. get_or_create_customer).
        referral_code: getStartParam() ?? null,
        customer_name: customerName.trim(),
        customer_contact: customerContact.trim(),
        delivery_method_id: deliveryMethodId,
        delivery_address: needsAddress && !usingSavedAddress ? newAddressText.trim() : "",
        address_id: usingSavedAddress ? Number(addressChoice) : null,
        items: lines.map((l) => ({ product_id: l.product.id, quantity: l.quantity })),
      });

      // Сохранить новый адрес в книгу — отдельным вызовом, не блокирует
      // оформление заказа при ошибке (см. docs/TZ-02, ТЗ-2 п.4).
      if (needsAddress && !usingSavedAddress && saveNewAddress && telegramId) {
        api.addresses.create(telegramId, { label: "", text: newAddressText.trim(), is_default: addresses.length === 0 }).catch(() => {});
      }

      // Оплата — пока заглушка, вызывается сразу же (см. app/payments.py,
      // StubPaymentProvider). Когда подключится ЮKassa, здесь появится
      // редирект на форму оплаты вместо прямого вызова.
      await api.orders.pay(order.id);

      hapticSuccess();
      clear();
      navigate(`/orders/${order.id}`, { replace: true });
    } catch (err) {
      hapticError();
      setSubmitError(
        err instanceof ApiError
          ? typeof err.detail === "string"
            ? err.detail
            : "Не удалось оформить заказ."
          : "Не удалось оформить заказ. Проверьте соединение.",
      );
      setSubmitting(false);
    }
  }

  return (
    <div>
      <PageHeader title="Оформление заказа" />

      {loading && <Loading />}
      {loadError && <ErrorBanner message={loadError} />}

      {!loading && !loadError && (
        <>
          <div className="field">
            <label>Как к вам обращаться</label>
            <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Имя" />
          </div>
          <div className="field">
            <label>Контакт (телефон или @username)</label>
            <input value={customerContact} onChange={(e) => setCustomerContact(e.target.value)} placeholder="+7… или @username" />
          </div>

          <h3 style={{ marginTop: 20 }}>Способ доставки</h3>
          {methods?.map((m) => (
            <label key={m.id} className={`radio-card ${deliveryMethodId === m.id ? "selected" : ""}`}>
              <input
                type="radio"
                name="delivery"
                checked={deliveryMethodId === m.id}
                onChange={() => setDeliveryMethodId(m.id)}
              />
              <div className="radio-card-body">
                <div className="radio-card-title">{m.name}</div>
                {m.description && <div className="radio-card-desc">{m.description}</div>}
              </div>
              <div className="radio-card-cost">{m.cost_type === "free" ? "бесплатно" : formatPrice(m.fixed_cost ?? 0)}</div>
            </label>
          ))}

          {needsAddress && (
            <>
              <h3 style={{ marginTop: 20 }}>Адрес доставки</h3>
              {addresses.map((a) => (
                <label key={a.id} className={`radio-card ${addressChoice === String(a.id) ? "selected" : ""}`}>
                  <input
                    type="radio"
                    name="address"
                    checked={addressChoice === String(a.id)}
                    onChange={() => setAddressChoice(String(a.id))}
                  />
                  <div className="radio-card-body">
                    <div className="radio-card-title">{a.label || "Адрес"}</div>
                    <div className="radio-card-desc">{a.text}</div>
                  </div>
                </label>
              ))}
              <label className={`radio-card ${addressChoice === NEW_ADDRESS ? "selected" : ""}`}>
                <input
                  type="radio"
                  name="address"
                  checked={addressChoice === NEW_ADDRESS}
                  onChange={() => setAddressChoice(NEW_ADDRESS)}
                />
                <div className="radio-card-body">
                  <div className="radio-card-title">Новый адрес</div>
                </div>
              </label>
              {addressChoice === NEW_ADDRESS && (
                <div className="field" style={{ marginTop: 8 }}>
                  <textarea
                    value={newAddressText}
                    onChange={(e) => setNewAddressText(e.target.value)}
                    placeholder="Город, улица, дом, квартира"
                  />
                  {telegramId && (
                    <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8, fontSize: "0.85rem", color: "var(--ink-muted)" }}>
                      <input type="checkbox" checked={saveNewAddress} onChange={(e) => setSaveNewAddress(e.target.checked)} />
                      Сохранить адрес в книгу
                    </label>
                  )}
                </div>
              )}
            </>
          )}

          <div style={{ marginTop: 20 }}>
            <div className="summary-row">
              <span>Товары</span>
              <span>{formatPrice(totalPrice)}</span>
            </div>
            <div className="summary-row">
              <span>Доставка</span>
              <span>{selectedMethod?.cost_type === "free" ? "бесплатно" : formatPrice(deliveryCost)}</span>
            </div>
            <div className="summary-row total">
              <span>Итого</span>
              <span>{formatPrice(grandTotal)}</span>
            </div>
          </div>

          {submitError && <ErrorBanner message={submitError} />}

          <div style={{ marginTop: 16 }}>
            <button className="btn btn-primary" disabled={!canSubmit} onClick={handleSubmit}>
              {submitting ? "Оформляем…" : `Оплатить ${formatPrice(grandTotal)}`}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
