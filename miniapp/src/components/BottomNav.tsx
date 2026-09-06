import { NavLink } from "react-router-dom";
import { useCart } from "../state/CartContext";

const ITEMS = [
  { to: "/", label: "Каталог", num: "01", end: true },
  { to: "/cart", label: "Корзина", num: "02" },
  { to: "/orders", label: "Заказы", num: "03" },
  { to: "/profile", label: "Профиль", num: "04" },
];

export function BottomNav() {
  const { totalQuantity } = useCart();

  return (
    <nav className="bottom-nav">
      {ITEMS.map((item) => (
        <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => (isActive ? "active" : "")}>
          <span className="rubric-num">{item.num}</span>
          <span className="rubric-label">
            {item.label}
            {item.to === "/cart" && totalQuantity > 0 && <span className="cart-badge">{totalQuantity}</span>}
          </span>
        </NavLink>
      ))}
    </nav>
  );
}
