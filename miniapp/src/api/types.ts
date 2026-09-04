// Зеркало Pydantic-схем backend (../backend/app/schemas.py, ../backend/app/models.py).
// Держать в синхроне вручную — backend ещё не публикует OpenAPI-типы в сборку фронтенда.

export type ProductType = "issue" | "subscription" | "merch";
export type DeliveryCostType = "free" | "fixed" | "calculated";
export type OrderStatus = "new" | "paid" | "assembled" | "shipped" | "delivered" | "cancelled";
export type PaymentStatus = "pending" | "paid" | "failed";

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
  items: OrderItemIn[];
}

export interface OrderItemOut {
  product_id: number;
  title: string;
  price: string;
  quantity: number;
}

export interface Order {
  id: number;
  customer_id: number | null;
  customer_name: string;
  customer_contact: string;
  delivery_method_id: number;
  delivery_address: string;
  address_id: number | null;
  delivery_cost: string;
  items_total: string;
  total: string;
  status: OrderStatus;
  payment_status: PaymentStatus;
  tracking_number: string;
  cancel_reason: string;
  created_at: string;
  items: OrderItemOut[];
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
