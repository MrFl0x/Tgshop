import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { ErrorBanner, Loading } from "../components/Loading";
import { useAsync } from "../hooks/useAsync";
import { useCart } from "../state/CartContext";
import { formatPrice, productTypeLabel } from "../format";
import { hapticTap } from "../telegram";

export function ProductPage() {
  const { id } = useParams<{ id: string }>();
  const productId = Number(id);
  const navigate = useNavigate();
  const { add } = useCart();
  const [qty, setQty] = useState(1);
  const [added, setAdded] = useState(false);

  const { data: product, error, loading, reload } = useAsync(() => api.products.get(productId), [productId]);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} onRetry={reload} />;
  if (!product) return null;

  const outOfStock = product.stock !== null && product.stock <= 0;
  const maxQty = product.stock !== null ? Math.max(product.stock, 0) : 99;

  return (
    <div>
      <PageHeader title={product.title} />
      <div className="pd-cover">
        {product.cover_url ? <img src={product.cover_url} alt={product.title} /> : <span>{product.title}</span>}
      </div>
      <span className="product-type">{productTypeLabel(product.type)}</span>
      <div className="pd-price">{formatPrice(product.price)}</div>
      {product.description && <p className="pd-description">{product.description}</p>}
      {product.stock !== null && (
        <p style={{ color: "var(--ink-faint)", fontSize: "0.85rem" }}>
          {outOfStock ? "Нет в наличии" : `В наличии: ${product.stock}`}
        </p>
      )}

      {!outOfStock && (
        <div className="qty-row">
          <button className="qty-btn" onClick={() => setQty((q) => Math.max(1, q - 1))} aria-label="Меньше">
            −
          </button>
          <span className="qty-value">{qty}</span>
          <button
            className="qty-btn"
            onClick={() => setQty((q) => Math.min(maxQty, q + 1))}
            aria-label="Больше"
            disabled={qty >= maxQty}
          >
            +
          </button>
        </div>
      )}

      <button
        className="btn btn-primary"
        disabled={outOfStock}
        onClick={() => {
          add(product, qty);
          hapticTap();
          setAdded(true);
          setTimeout(() => navigate("/cart"), 350);
        }}
      >
        {outOfStock ? "Нет в наличии" : added ? "Добавлено ✓" : "В корзину"}
      </button>
    </div>
  );
}
