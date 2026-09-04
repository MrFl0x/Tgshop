import { Link, useNavigate } from "react-router-dom";
import { useCart } from "../state/CartContext";
import { formatPrice } from "../format";

export function CartPage() {
  const { lines, totalPrice, setQuantity, remove } = useCart();
  const navigate = useNavigate();

  if (lines.length === 0) {
    return (
      <div>
        <h1 style={{ marginBottom: 16 }}>Корзина</h1>
        <div className="empty-state">
          Корзина пуста.
          <div style={{ marginTop: 16 }}>
            <Link to="/" className="btn btn-secondary" style={{ display: "inline-flex" }}>
              В каталог
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ marginBottom: 12 }}>Корзина</h1>

      <div>
        {lines.map(({ product, quantity }) => (
          <div className="cart-line" key={product.id}>
            <div className="cart-line-cover">
              {product.cover_url && <img src={product.cover_url} alt={product.title} />}
            </div>
            <div className="cart-line-info">
              <div className="cart-line-title">{product.title}</div>
              <div className="cart-line-price">{formatPrice(product.price)}</div>
              <div className="cart-line-qty">
                <button className="qty-btn" onClick={() => setQuantity(product.id, quantity - 1)}>
                  −
                </button>
                <span className="qty-value">{quantity}</span>
                <button
                  className="qty-btn"
                  onClick={() => setQuantity(product.id, quantity + 1)}
                  disabled={product.stock !== null && quantity >= product.stock}
                >
                  +
                </button>
                <button className="cart-remove" onClick={() => remove(product.id)}>
                  Убрать
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 16 }}>
        <div className="summary-row total">
          <span>Итого</span>
          <span>{formatPrice(totalPrice)}</span>
        </div>
      </div>

      <div style={{ marginTop: 20 }}>
        <button className="btn btn-primary" onClick={() => navigate("/checkout")}>
          Оформить заказ
        </button>
      </div>
    </div>
  );
}
