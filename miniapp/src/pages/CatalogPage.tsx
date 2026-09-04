import { api } from "../api/client";
import { ProductCard } from "../components/ProductCard";
import { ErrorBanner, Loading } from "../components/Loading";
import { useAsync } from "../hooks/useAsync";

export function CatalogPage() {
  const { data: products, error, loading, reload } = useAsync(() => api.products.list(), []);

  return (
    <div>
      <p className="eyebrow">Каталог</p>
      <h1 style={{ marginBottom: 16 }}>
        Магазин <em style={{ color: "var(--accent)", fontStyle: "italic" }}>«Чтиво»</em>
      </h1>

      {loading && <Loading />}
      {error && <ErrorBanner message={error} onRetry={reload} />}
      {!loading && !error && products && products.length === 0 && (
        <div className="empty-state">Пока нет доступных товаров — загляните позже.</div>
      )}
      {products && products.length > 0 && (
        <div className="product-grid">
          {products.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      )}
    </div>
  );
}
