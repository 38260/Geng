/**
 * 收藏的页面侧状态。
 *
 * 每次进页面都从 storage 重读一遍：小程序页面栈里多个页面可能同时持有收藏，
 * 在详情页加了收藏，回到梗库要能看到。
 */
import Taro from "@tarojs/taro";
import { useCallback, useMemo, useState } from "react";

import {
  clearFavorites,
  FavoriteItem,
  loadFavorites,
  toggleFavorite,
} from "@/utils/favorites";
import { taroStore } from "@/utils/store-taro";

export function useFavorites() {
  const [items, setItems] = useState<FavoriteItem[]>(() => loadFavorites(taroStore));
  const idSet = useMemo(() => new Set(items.map((row) => row.id)), [items]);

  const toggle = useCallback((meme: { id: number; name: string }) => {
    const result = toggleFavorite(taroStore, meme);
    setItems(result.items);
    Taro.showToast({ title: result.added ? "已收藏（只存在本机）" : "已取消收藏", icon: "none" });
    return result.added;
  }, []);

  const clear = useCallback(() => {
    clearFavorites(taroStore);
    setItems([]);
  }, []);

  const reload = useCallback(() => setItems(loadFavorites(taroStore)), []);

  return {
    items,
    count: items.length,
    has: (id: number) => idSet.has(id),
    /** 逗号分隔，直接喂给 /api/memes?ids= */
    idParam: items.map((row) => row.id).join(","),
    toggle,
    clear,
    reload,
  };
}
