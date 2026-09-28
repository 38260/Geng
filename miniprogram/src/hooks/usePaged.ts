import { useCallback, useEffect, useRef, useState } from "react";
import Taro from "@tarojs/taro";

import { describeError } from "@/api/client";
import type { MemeCard, MemeList } from "@/types/api";

export interface Paged {
  items: MemeCard[];
  total: number;
  gatedOut: number;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  /** 触底加载下一页；没有更多了返回 false */
  loadMore: () => Promise<void>;
  refresh: () => Promise<void>;
}

/**
 * 分页列表。
 *
 * 换筛选条件时重新从第一页开始；触底只往后追加，
 * 追加失败不清空已有内容（用户已经看到的东西不该因为一次网络抖动消失）。
 */
export function usePaged(fetch: (offset: number, limit: number) => Promise<MemeList>, deps: unknown[]): Paged {
  const [items, setItems] = useState<MemeCard[]>([]);
  const [total, setTotal] = useState(0);
  const [gatedOut, setGatedOut] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const offset = useRef(0);
  const busy = useRef(false);
  const alive = useRef(true);
  const fetchRef = useRef(fetch);
  fetchRef.current = fetch;

  const LIMIT = 20;

  const run = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    setLoading(true);
    setError(null);
    try {
      const first = await fetchRef.current(0, LIMIT);
      if (!alive.current) return;
      setItems(first.items);
      setTotal(first.total);
      setGatedOut(first.gated_out ?? 0);
      offset.current = first.items.length;
    } catch (inner) {
      if (alive.current) setError(describeError(inner));
    } finally {
      if (alive.current) setLoading(false);
      busy.current = false;
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    offset.current = 0;
    run();
    return () => {
      alive.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const loadMore = useCallback(async () => {
    if (busy.current || offset.current >= total) return;
    busy.current = true;
    setLoadingMore(true);
    try {
      const next = await fetchRef.current(offset.current, LIMIT);
      if (!alive.current) return;
      setItems((prev) => {
        const seen = new Set(prev.map((row) => row.id));
        return [...prev, ...next.items.filter((row) => !seen.has(row.id))];
      });
      offset.current += next.items.length;
      if (!next.items.length) offset.current = total; // 拿不到新东西就别再空转
    } catch (inner) {
      if (alive.current) Taro.showToast({ title: describeError(inner), icon: "none" });
    } finally {
      if (alive.current) setLoadingMore(false);
      busy.current = false;
    }
  }, [total]);

  const refresh = useCallback(async () => {
    offset.current = 0;
    await run();
  }, [run]);

  return { items, total, gatedOut, loading, loadingMore, error, loadMore, refresh };
}
