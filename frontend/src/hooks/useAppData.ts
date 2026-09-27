import { useCallback, useEffect, useState } from "react";

import { api } from "@/api/client";
import type { Meta } from "@/types/api";

let cached: Meta | null = null;
let inflight: Promise<Meta> | null = null;

function load(): Promise<Meta> {
  if (cached) return Promise.resolve(cached);
  if (!inflight) {
    inflight = api.meta().then((meta) => {
      cached = meta;
      inflight = null;
      return meta;
    });
  }
  return inflight;
}

/** 全站共享的元信息（数据来源 / 更新时间 / 透明度文案）。 */
export function useMeta() {
  const [meta, setMeta] = useState<Meta | null>(cached);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    load()
      .then((value) => alive && setMeta(value))
      .catch(() => alive && setError("无法读取数据源信息"));
    return () => {
      alive = false;
    };
  }, []);

  return { meta, error };
}

const KEY = "gengcha…list";

export interface Favorite {
  id: number;
  name: string;
  added_at: string;
}

function read(): Favorite[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? (JSON.parse(raw) as Favorite[]) : [];
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item?.id === "number") : [];
  } catch {
    return [];
  }
}

/**
 * 我的收藏：只存在浏览器本地，没有账号体系（V1 明确不做用户系统）。
 */
export function useFavorites() {
  const [items, setItems] = useState<Favorite[]>(read);

  useEffect(() => {
    const sync = () => setItems(read());
    window.addEventListener("storage", sync);
    window.addEventListener("gengchao:favorites", sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener("gengchao:favorites", sync);
    };
  }, []);

  const persist = (next: Favorite[]) => {
    localStorage.setItem(KEY, JSON.stringify(next));
    setItems(next);
    window.dispatchEvent(new Event("gengchao:favorites"));
  };

  const toggle = useCallback(
    (id: number, name: string) => {
      const current = read();
      const exists = current.some((item) => item.id === id);
      persist(
        exists
          ? current.filter((item) => item.id !== id)
          : [{ id, name, added_at: new Date().toISOString() }, ...current],
      );
    },
    [],
  );

  const clear = useCallback(() => persist([]), []);

  return { items, ids: new Set(items.map((item) => item.id)), toggle, clear };
}
