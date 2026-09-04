import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ErrorBanner, Loading } from "../components/Loading";
import { useAsync } from "../hooks/useAsync";
import { formatDate, formatPrice, orderStatusLabel } from "../format";
import { getCurrentUserId } from "../telegram";

export function OrdersListPage() {
  const telegramId = getCurrentUserId();
  const { data: orders, error, loading, reload } = useAsync(
    () => (telegramId ? api.customers.orders(telegramId) : Promise.resolve([])),
    [telegramId],
  );

  return (
    <div>
      <h1 style={{ marginBottom: 16 }}>Мои заказы</h1>

      {!telegramId && <ErrorBanner message="Откройте магазин через бота в Telegram, чтобы видеть свои заказы." />}
      {loading && <Loading />}
      {error && <ErrorBanner message={error} onRetry={reload} />}
      {orders && orders.length === 0 && <div className="empty-state">Заказов пока нет.</div>}

      {orders?.map((order) => (
        <Link key={order.id} to={`/orders/${order.id}`} className="order-card">
          <div className="order-card-top">
            <span className="order-card-num">№{order.id}</span>
            <span className="order-card-total">{formatPrice(order.total)}</span>
          </div>
          <div className="order-card-meta">
            {formatDate(order.created_at)} · <span className={`status-badge ${order.status}`}>{orderStatusLabel(order.status)}</span>
          </div>
        </Link>
      ))}
    </div>
  );
}
