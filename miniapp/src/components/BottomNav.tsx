import { NavLink } from "react-router-dom";
import { useCart } from "../state/CartContext";

const ITEMS = [
  { to: "/", label: "Каталог", icon: "📚", end: true },
  { to: "/cart", label: "Корзина", icon: "🛒" },
  { to: "/orders", label: "Заказы", icon: "📦" },
  { to: "/profile", label: "Профиль", icon: "👤" },
];

export function BottomNav() {
  const { totalQuantity } = useCart();

  return (
    <nav className="bottom-nav">
      {ITEMS.map((item) => (
        <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => (isActive ? "active" : "")}>
          <span className="icon">
            {item.icon}
            {item.to === "/cart" && totalQuantity > 0 && <span className="cart-badge">{totalQuantity}</span>}
          </span>
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
