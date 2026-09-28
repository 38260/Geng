/**
 * 页面跳转的小工具。
 *
 * tabBar 页面只能用 `switchTab` 跳转，而 `switchTab` 不支持带 query，
 * 所以"从详情页跳到梗库并搜这个梗"要先把手帕放进 storage，
 * 梗库在 `useDidShow` 里取走并清空——取一次就清，避免下次进梗库还被上次的词过滤着。
 */
import Taro from "@tarojs/taro";

const LIBRARY_QUERY_KEY = "library_query";

export async function openLibrarySearch(keyword: string): Promise<void> {
  try {
    Taro.setStorageSync(LIBRARY_QUERY_KEY, keyword);
  } catch {
    // 写不进去也要跳过去，只是不带搜索词
  }
  await Taro.switchTab({ url: "/pages/library/index" });
}

/** 取走并清空待用的搜索词。 */
export function takeLibraryQuery(): string {
  try {
    const value = Taro.getStorageSync(LIBRARY_QUERY_KEY);
    if (typeof value === "string" && value) {
      Taro.removeStorageSync(LIBRARY_QUERY_KEY);
      return value;
    }
  } catch {
    /* 忽略：拿不到就当没有 */
  }
  return "";
}
