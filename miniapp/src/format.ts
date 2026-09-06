export function formatPrice(value: string | number): string {
  const num = Number(value);
  return `${num.toLocaleString("ru-RU", { maximumFractionDigits: 0 })} ₽`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const PRODUCT_TYPE_LABELS: Record<string, string> = {
  issue: "Номер",
  subscription: "Подписка",
  merch: "Мерч",
};

export function productTypeLabel(type: string): string {
  return PRODUCT_TYPE_LABELS[type] ?? type;
}

const ORDER_STATUS_LABELS: Record<string, string> = {
  awaiting_payment: "Ожидает оплаты",
  awaiting_packaging: "Собираем",
  awaiting_deliver: "Ждёт отгрузки",
  delivering: "В пути",
  delivered: "Вручён",
  cancelled: "Отменён",
  returned: "Возврат",
};

export function orderStatusLabel(status: string): string {
  return ORDER_STATUS_LABELS[status] ?? status;
}
