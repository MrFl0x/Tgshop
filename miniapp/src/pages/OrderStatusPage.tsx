import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { ErrorBanner, Loading } from "../components/Loading";
import { useAsync } from "../hooks/useAsync";
import { formatDate, formatPrice, orderStatusLabel } from "../format";

export function OrderStatusPage() {
  const { id } = useParams<{ id: string }>();
  const orderId = Number(id);

  const { data: order, error: orderError, loading: orderLoading, reload: reloadOrder } = useAsync(
    () => api.orders.get(orderId),
    [orderId],
  );
  const { data: history, error: historyError, loading: historyLoading } = useAsync(
    () => api.orders.history(orderId),
    [orderId],
  );

  if (orderLoading) return <Loading />;
  if (orderError) return <ErrorBanner message={orderError} onRetry={reloadOrder} />;
  if (!order) return null;

  return (
    <div>
      <PageHeader title={`Заказ ${order.number}`} />

      <span className={`status-badge ${order.status}`}>{orderStatusLabel(order.status)}</span>
      {order.tracking_number && (
        <p style={{ marginTop: 10 }}>
          Трек-номер: <span className="mono">{order.tracking_number}</span>
        </p>
      )}

      <h3 style={{ marginTop: 24 }}>Состав заказа</h3>
      {order.items.map((item) => (
        <div key={item.product_id} className="summary-row">
          <span>
            {item.title} × {item.quantity}
          </span>
          <span>{formatPrice(item.subtotal)}</span>
        </div>
      ))}
      {Number(order.discount_total) > 0 && (
        <div className="summary-row" style={{ color: "var(--danger)" }}>
          <span>Скидка{order.promo_code ? ` по промокоду «${order.promo_code}»` : ""}</span>
          <span>-{formatPrice(order.discount_total)}</span>
        </div>
      )}
      <div className="summary-row">
        <span>Доставка</span>
        <span>{formatPrice(order.delivery_cost)}</span>
      </div>
      <div className="summary-row total">
        <span>Итого</span>
        <span>{formatPrice(order.total)}</span>
      </div>

      {order.delivery_address && (
        <>
          <h3 style={{ marginTop: 20 }}>Адрес доставки</h3>
          <p style={{ color: "var(--ink-muted)" }}>{order.delivery_address}</p>
        </>
      )}
      {order.customer_comment && (
        <>
          <h3 style={{ marginTop: 20 }}>Комментарий к заказу</h3>
          <p style={{ color: "var(--ink-muted)" }}>{order.customer_comment}</p>
        </>
      )}

      <h3 style={{ marginTop: 20 }}>История статусов</h3>
      {historyLoading && <Loading />}
      {historyError && <ErrorBanner message={historyError} />}
      {history && history.length > 0 && (
        <ul className="timeline">
          {history.map((h) => (
            <li key={h.id}>
              <div>
                <div className="timeline-status">{orderStatusLabel(h.to_status)}</div>
                <div className="timeline-meta">
                  {formatDate(h.created_at)}
                  {h.note ? ` · ${h.note}` : ""}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
