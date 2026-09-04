export function Loading() {
  return <div className="spinner-row">Загрузка…</div>;
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="callout" style={{ borderLeftColor: "var(--danger)" }}>
      <p style={{ margin: 0 }}>{message}</p>
      {onRetry && (
        <button className="btn btn-secondary btn-sm" style={{ marginTop: 10 }} onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  );
}
