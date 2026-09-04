import { getInitData } from "../telegram";
import type {
  Address,
  Customer,
  DeliveryMethod,
  Order,
  OrderCreateIn,
  OrderStatusHistoryEntry,
  Product,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Ошибка запроса (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

/** true — эндпоинту не нужен X-Telegram-Init-Data (каталог, доставка).
 * Для всех остальных заголовок добавляется всегда, даже если initData
 * пуст (пустой — backend сам ответит 401, это ожидаемо вне Telegram). */
async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  const { method = "GET", body, auth = true } = options;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) headers["X-Telegram-Init-Data"] = getInitData();

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  products: {
    list: () => request<Product[]>("/products/", { auth: false }),
    get: (id: number) => request<Product>(`/products/${id}`, { auth: false }),
  },
  deliveryMethods: {
    list: () => request<DeliveryMethod[]>("/delivery-methods/", { auth: false }),
  },
  addresses: {
    list: (telegramId: string) => request<Address[]>(`/customers/${telegramId}/addresses/`),
    create: (telegramId: string, body: { label: string; text: string; is_default: boolean }) =>
      request<Address>(`/customers/${telegramId}/addresses/`, { method: "POST", body }),
    remove: (telegramId: string, addressId: number) =>
      request<void>(`/customers/${telegramId}/addresses/${addressId}`, { method: "DELETE" }),
  },
  orders: {
    create: (body: OrderCreateIn) => request<Order>("/orders/", { method: "POST", body }),
    pay: (orderId: number) => request<Order>(`/orders/${orderId}/pay`, { method: "POST" }),
    get: (orderId: number) => request<Order>(`/orders/${orderId}`),
    history: (orderId: number) => request<OrderStatusHistoryEntry[]>(`/orders/${orderId}/history`),
  },
  customers: {
    profile: (telegramId: string) => request<Customer>(`/customers/${telegramId}`),
    orders: (telegramId: string) => request<Order[]>(`/customers/${telegramId}/orders`),
  },
};
