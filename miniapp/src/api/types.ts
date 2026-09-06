// Зеркало Pydantic-схем backend (../backend/app/schemas.py, ../backend/app/models.py).
// Держать в синхроне вручную — backend ещё не публикует OpenAPI-типы в сборку фронтенда.

export type ProductType = "issue" | "subscription" | "merch";
export type DeliveryCostType = "free" | "fixed" | "calculated";
// Ozon-style статусы (см. tz-zakazy.md, backend-миграция 3f0a1c7e2b6d) —
// awaiting_payment → awaiting_packaging → awaiting_deliver → delivering →
// delivered, плюс cancelled/returned как боковые ветки.
export type OrderStatus =
  | "awaiting_payment"
  | "awaiting_packaging"
  | "awaiting_deliver"
  | "delivering"
  | "delivered"
  | "cancelled"
  | "returned";
export type PaymentStatus = "pending" | "paid" | "failed" | "refunded";

export interface Product {
  id: number;
  title: string;
  type: ProductType;
  description: string;
  cover_url: string;
  price: string; // Decimal сериализуется строкой
  stock: number | null;
  is_active: boolean;
}

export interface DeliveryMethod {
  id: number;
  name: string;
  code: string;
  description: string;
  cost_type: DeliveryCostType;
  fixed_cost: string | null;
  requires_address: boolean;
  is_active: boolean;
}

export interface Address {
  id: number;
  label: string;
  text: string;
  is_default: boolean;
}

export interface OrderItemIn {
  product_id: number;
  quantity: number;
}

export interface OrderCreateIn {
  referral_code?: string | null;
  customer_name: string;
  customer_contact: string;
  delivery_method_id: number;
  delivery_address: string;
  address_id?: number | null;
  promo_code?: string | null;
  customer_comment?: string;
  items: OrderItemIn[];
}

export interface OrderItemOut {
  product_id: number;
  title: string;
  price: string;
  quantity: number;
  subtotal: string;
}

export interface ReturnOut {
  id: number;
  reason: string;
  status: "requested" | "approved" | "rejected" | "completed";
  comment: string;
  created_at: string;
}

export interface Order {
  id: number;
  number: string;
  customer_id: number | null;
  customer_name: string;
  customer_contact: string;
  delivery_method_id: number;
  delivery_address: string;
  address_id: number | null;
  pickup_point: string;
  delivery_cost: string;
  items_total: string;
  discount_total: string;
  promo_code: string | null;
  total: string;
  status: OrderStatus;
  payment_status: PaymentStatus;
  payment_method: string;
  tracking_number: string;
  customer_comment: string;
  cancel_reason: string;
  created_at: string;
  items: OrderItemOut[];
  returns: ReturnOut[];
}

export interface PromoCodeOut {
  code: string;
  discount_type: "percent" | "fixed";
  discount_value: string;
}

export interface OrderStatusHistoryEntry {
  id: number;
  from_status: OrderStatus | null;
  to_status: OrderStatus;
  changed_by: string;
  note: string;
  created_at: string;
}

export interface Customer {
  id: number;
  full_name: string;
  contact: string;
  referral_code: string | null;
  bonus_balance: string;
}
