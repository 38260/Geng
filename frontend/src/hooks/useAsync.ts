import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
  setData: (updater: T) => void;
}

/**
 * 统一的取数状态机。
 *
 * 页面永远有三种状态（loading / error / data），不会出现白屏或 undefined。
 */
export function useAsync<T>(fetcher: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setDataState] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetcher()
      .then((result) => {
        if (cancelled || !mounted.current) return;
        setDataState(result);
      })
      .catch((err: unknown) => {
        if (cancelled || !mounted.current) return;
        setError(err instanceof ApiError ? err.detail : "数据加载失败");
      })
      .finally(() => {
        if (!cancelled && mounted.current) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);
  const setData = useCallback((value: T) => setDataState(value), []);

  return { data, loading, error, reload, setData };
}
