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

/**
 * 点一条相关视频：H5 直接开新标签；微信小程序开不了站外链接，只能把地址复制好。
 *
 * 不是偷懒：<web-view> 要求把 bilibili.com 配成小程序"业务域名"并上传校验文件，
 * 域名不归我们所有，配不上；跳 B 站官方小程序要对方 appId 且必须真机核验。
 * 所以微信端把话说清楚——链接已经复制，去浏览器粘贴，别让人以为点了没反应。
 */
export function openVideoUrl(url: string): void {
  if (!url) {
    Taro.showToast({ title: "这条没有真实链接（演示数据）", icon: "none" });
    return;
  }
  if (process.env.TARO_ENV === "h5") {
    window.open(url, "_blank");
    return;
  }
  Taro.setClipboardData({
    data: url,
    success: () => Taro.showToast({ title: "链接已复制 · 请在浏览器打开", icon: "none" }),
    fail: () => Taro.showToast({ title: "复制失败，请手动长按复制", icon: "none" }),
  });
}

/** 同一句"能不能真打开"的判断，界面文案要用它，别两边写歪。 */
export function videoOpensExternally(): boolean {
  return process.env.TARO_ENV === "h5";
}
