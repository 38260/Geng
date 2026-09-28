/**
 * 收藏：只存在这台设备上。
 *
 * V1 不做账号体系，所以收藏没有服务端副本，也不跨端同步（Web 端那份在
 * localStorage 里，两边互不可见）。这点必须在界面上写清楚，不能让用户
 * 以为换了手机还能看到。
 *
 * 存的是 id + 名字 + 收藏时间，**不存梗的数据副本**：热度每天都在变，
 * 收藏页要的是实时数，所以列表靠 `/api/memes?ids=` 现取。
 */
export interface FavoriteItem {
  id: number;
  name: string;
  at: string;
}

/** 可注入的存储，方便单测里用内存对象跑，不用起小程序环境。 */
export interface KV {
  get(key: string): string | null;
  set(key: string, value: string): void;
  remove(key: string): void;
}

export const FAVORITES_KEY = "favorites";

export function loadFavorites(store: KV): FavoriteItem[] {
  const raw = store.get(FAVORITES_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // id 必须是正整数（库里 id 从 1 起）；0、字符串、小数都当脏数据丢掉
    return parsed
      .filter((row) => row && Number.isInteger(row.id) && row.id > 0 && row.name)
      .map((row) => ({ id: row.id, name: String(row.name), at: String(row.at || "") }));
  } catch {
    // 手改过 storage 或版本不兼容：宁可清空重来，也不让收藏页白屏
    return [];
  }
}

function save(store: KV, items: FavoriteItem[]): void {
  if (!items.length) {
    store.remove(FAVORITES_KEY);
    return;
  }
  store.set(FAVORITES_KEY, JSON.stringify(items));
}

export function isFavorite(store: KV, id: number): boolean {
  return loadFavorites(store).some((row) => row.id === id);
}

/** 返回操作后的完整列表与"这次是加还是删"。 */
export function toggleFavorite(
  store: KV,
  meme: { id: number; name: string },
  now = new Date(),
): { added: boolean; items: FavoriteItem[] } {
  const items = loadFavorites(store);
  const index = items.findIndex((row) => row.id === meme.id);
  if (index >= 0) {
    items.splice(index, 1);
    save(store, items);
    return { added: false, items };
  }
  const at = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(
    now.getDate(),
  ).padStart(2, "0")}`;
  const next = [{ id: meme.id, name: meme.name, at }, ...items];
  save(store, next);
  return { added: true, items: next };
}

export function favoriteIds(store: KV): number[] {
  return loadFavorites(store).map((row) => row.id);
}

export function clearFavorites(store: KV): void {
  store.remove(FAVORITES_KEY);
}
