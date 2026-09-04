import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Product } from "../api/types";

export interface CartLine {
  product: Product;
  quantity: number;
}

interface CartContextValue {
  lines: CartLine[];
  totalQuantity: number;
  totalPrice: number;
  add: (product: Product, quantity?: number) => void;
  setQuantity: (productId: number, quantity: number) => void;
  remove: (productId: number) => void;
  clear: () => void;
}

const CartContext = createContext<CartContextValue | null>(null);

const STORAGE_KEY = "chtivo_cart_v1";

// Корзина — локальное состояние на устройстве, не хранится на backend, пока
// заказ не оформлен (см. docs/TZ-02-bot-i-miniapp.md, ТЗ-2 п.3). localStorage
// — только чтобы не терять корзину при случайном закрытии Mini App, не
// синхронизация между устройствами.
function loadInitial(): CartLine[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as CartLine[];
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>(loadInitial);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(lines));
    } catch {
      // localStorage недоступен (приватный режим и т.п.) — корзина просто
      // не переживёт перезагрузку, ничего не ломаем.
    }
  }, [lines]);

  const value = useMemo<CartContextValue>(() => {
    const totalQuantity = lines.reduce((sum, l) => sum + l.quantity, 0);
    const totalPrice = lines.reduce((sum, l) => sum + Number(l.product.price) * l.quantity, 0);

    return {
      lines,
      totalQuantity,
      totalPrice,
      add: (product, quantity = 1) =>
        setLines((prev) => {
          const existing = prev.find((l) => l.product.id === product.id);
          if (existing) {
            return prev.map((l) =>
              l.product.id === product.id ? { ...l, quantity: l.quantity + quantity } : l,
            );
          }
          return [...prev, { product, quantity }];
        }),
      setQuantity: (productId, quantity) =>
        setLines((prev) =>
          quantity <= 0
            ? prev.filter((l) => l.product.id !== productId)
            : prev.map((l) => (l.product.id === productId ? { ...l, quantity } : l)),
        ),
      remove: (productId) => setLines((prev) => prev.filter((l) => l.product.id !== productId)),
      clear: () => setLines([]),
    };
  }, [lines]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart используется вне CartProvider");
  return ctx;
}
