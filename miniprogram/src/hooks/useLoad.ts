/**
 * 一个极简的"加载—重试"hook。
 *
 * 不引 react-query：小程序包体敏感，而这里只需要 loading / error / reload 三件事。
 */
import Taro from "@tarojs/taro";
import { useCallback, useEffect, useRef, useState } from "react";

import { describeError } from "@/api/client";

export interface LoadState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
  setData: (updater: (prev: T | null) => T) => void;
}

export function useLoad<T>(loader: () => Promise<T>, deps: unknown[]): LoadState<T> {
  const [data, setDataState] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const alive = useRef(true);
  const loadRef = useRef(loader);
  loadRef.current = loader;

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await loadRef.current();
      if (alive.current) setDataState(next);
    } catch (inner) {
      if (alive.current) setError(describeError(inner));
    } finally {
      if (alive.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    run();
    return () => {
      alive.current = false;
    };
    // deps 由调用方决定（页面 id / 筛选条件），这里刻意不深比较
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const setData = useCallback((updater: (prev: T | null) => T) => {
    setDataState((prev) => updater(prev));
  }, []);

  return { data, loading, error, reload: run, setData };
}

/** 复制一段文本并给出反馈（小程序没有 window.navigator.clipboard）。 */
export function copyText(text: string): void {
  Taro.setClipboardData({ data: text }).then(
    () => Taro.showToast({ title: "已复制", icon: "none" }),
    () => Taro.showToast({ title: "复制失败", icon: "none" }),
  );
}
