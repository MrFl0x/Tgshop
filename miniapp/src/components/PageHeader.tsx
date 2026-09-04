import { useNavigate } from "react-router-dom";
import type { ReactNode } from "react";

export function PageHeader({ title, back = true, action }: { title: string; back?: boolean; action?: ReactNode }) {
  const navigate = useNavigate();
  return (
    <div className="page-header">
      {back && (
        <button className="back-btn" onClick={() => navigate(-1)} aria-label="Назад">
          ←
        </button>
      )}
      <h1 style={{ flex: 1 }}>{title}</h1>
      {action}
    </div>
  );
}
