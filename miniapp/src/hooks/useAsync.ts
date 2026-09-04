import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";

interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

/** Общий паттерн загрузки для страниц: вызывает fn при монтировании и при
 * смене deps, отдаёт data/loading/error и reload() для кнопки «Повторить».
 * Не кеширует между страницами — для объёма данных этого MVP не нужно. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  const load = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fn()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError) {
          if (err.status === 401) setError("Не удалось подтвердить, что это вы — откройте магазин заново через бота.");
          else if (err.status === 404) setError("Не найдено.");
          else setError(typeof err.detail === "string" ? err.detail : "Не удалось загрузить данные.");
        } else {
          setError("Не удалось загрузить данные. Проверьте соединение.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  useEffect(() => load(), [load]);

  return { data, error, loading, reload: () => setTick((t) => t + 1) };
}
