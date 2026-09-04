import { useState } from "react";
import { api } from "../api/client";
import { ErrorBanner, Loading } from "../components/Loading";
import { useAsync } from "../hooks/useAsync";
import { formatPrice } from "../format";
import { getCurrentUserId, hapticTap } from "../telegram";

const BOT_USERNAME = import.meta.env.VITE_BOT_USERNAME;

export function ProfilePage() {
  const telegramId = getCurrentUserId();
  const { data: profile, error, loading, reload } = useAsync(
    () => (telegramId ? api.customers.profile(telegramId) : Promise.resolve(null)),
    [telegramId],
  );
  const [copied, setCopied] = useState(false);

  if (!telegramId) {
    return (
      <div>
        <h1 style={{ marginBottom: 16 }}>Профиль</h1>
        <ErrorBanner message="Откройте магазин через бота в Telegram, чтобы увидеть профиль." />
      </div>
    );
  }

  if (loading) return <Loading />;

  // 404 от GET /customers/{telegram_id} — у клиента ещё нет ни одного
  // заказа/адреса, профиль физически не заведён (см. routers/customers.py).
  // Не ошибка, а нормальное состояние «нового» читателя.
  const isNewCustomer = error === "Не найдено.";

  if (error && !isNewCustomer) return <ErrorBanner message={error} onRetry={reload} />;

  const referralLink = profile?.referral_code && BOT_USERNAME ? `https://t.me/${BOT_USERNAME}?start=${profile.referral_code}` : null;

  return (
    <div>
      <h1 style={{ marginBottom: 16 }}>Профиль</h1>

      <div className="profile-card">
        <div style={{ color: "var(--ink-muted)", fontSize: "0.85rem" }}>Бонусный баланс</div>
        <div className="bonus-amount">{formatPrice(profile?.bonus_balance ?? 0)}</div>
        {isNewCustomer && (
          <p style={{ color: "var(--ink-faint)", fontSize: "0.82rem", margin: 0 }}>
            Появится после первого заказа
          </p>
        )}
      </div>

      <h3>Реферальная ссылка</h3>
      <p style={{ color: "var(--ink-muted)", fontSize: "0.88rem" }}>
        Пригласите друга — после его первой оплаты вы оба получите бонус на счёт.
      </p>
      {referralLink ? (
        <div className="referral-box">
          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>{referralLink}</span>
          <button
            className="copy-btn"
            onClick={() => {
              navigator.clipboard?.writeText(referralLink).catch(() => {});
              hapticTap();
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }}
          >
            {copied ? "Скопировано" : "Копировать"}
          </button>
        </div>
      ) : (
        <p style={{ color: "var(--ink-faint)", fontSize: "0.82rem" }}>
          Ссылка появится после первого заказа — реферальный код заводится вместе с профилем.
        </p>
      )}
    </div>
  );
}
