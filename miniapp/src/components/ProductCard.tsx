import { Link } from "react-router-dom";
import type { Product } from "../api/types";
import { formatPrice, productTypeLabel } from "../format";

export function ProductCard({ product }: { product: Product }) {
  const lowStock = product.stock !== null && product.stock <= 5;
  return (
    <Link to={`/product/${product.id}`} className="product-card">
      <div className="product-cover">
        {product.cover_url ? <img src={product.cover_url} alt={product.title} /> : <span>{product.title}</span>}
      </div>
      <div className="product-info">
        <span className="product-type">{productTypeLabel(product.type)}</span>
        <span className="product-title">{product.title}</span>
        <span className="product-price">{formatPrice(product.price)}</span>
        {product.stock !== null && (
          <span className={`product-stock ${lowStock ? "low" : ""}`}>
            {product.stock > 0 ? `осталось ${product.stock}` : "нет в наличии"}
          </span>
        )}
      </div>
    </Link>
  );
}
