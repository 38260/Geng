/**
 * 页面跳转的小工具。
 *
 * tabBar 页面只能用 `switchTab` 跳转，而 `switchTab` 不支持带 query，
 * 所以"从详情页跳到梗库并搜这个梗"要先把手帕放进 storage，
 * 梗库在 `useDidShow` 里取走并清空——取一次就清，避免下次进梗库还被上次的词过滤着。
 */
import Taro from "@tarojs/taro";

import { BILIBILI_MINIAPP_ID, bilibiliMiniProgramPath } from "@/utils/bilibili";

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
 * 点一条相关视频：H5 开新标签；微信里跳到「哔哩哔哩」小程序的播放页。
 *
 * 为什么不是直接在站内播：小程序不能打开站外链接，`<web-view>` 又要求把 bilibili.com
 * 配成"业务域名"并上传校验文件（域名不归我们所有，且个人主体小程序不支持 web-view）。
 * 但小程序之间可以直接跳：B 站的播放页在微信里是现成的，用户看完点左上角返回就回到这里，
 * 比"复制链接自己去浏览器粘贴"顺得多。
 *
 * 两点必须同时成立才能跳过去（否则微信回调 fail）：
 *   1. 目标 appId 声明在 app.config.ts 的 navigateToMiniProgramAppIdList 里；
 *   2. 用户点一下微信的确认弹窗（2.3.0 起强制，用户点取消会回调 fail cancel）。
 * 所以任何一步没过都要退回复制链接——宁可退回复制，也不能点了没反应。
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

  const path = bilibiliMiniProgramPath(url);
  if (!path) {
    copyVideoLink(url);
    return;
  }

  Taro.navigateToMiniProgram({
    appId: BILIBILI_MINIAPP_ID,
    path,
    envVersion: "release",
    fail: (err) => {
      // 用户自己点了"取消"就别再打扰；其余失败（没声明/目标不可用/版本过低）才退回复制
      if (/cancel/i.test(err?.errMsg || "")) return;
      copyVideoLink(url);
    },
  });
}

/** 跳不过去时的退路：地址放回剪贴板，并说清下一步。 */
function copyVideoLink(url: string): void {
  Taro.setClipboardData({
    data: url,
    success: () => Taro.showToast({ title: "跳转没成功，链接已复制", icon: "none" }),
    fail: () => Taro.showToast({ title: "复制失败，请手动长按复制", icon: "none" }),
  });
}

/** 行尾那两个字（打开 / 去 B 站），界面文案统一从这里取，别两边写歪。 */
export function videoActionWord(): string {
  return process.env.TARO_ENV === "h5" ? "打开" : "去 B 站";
}

/** 点一条视频会发生什么，一整句说清。 */
export function videoActionHint(): string {
  return process.env.TARO_ENV === "h5"
    ? "点一条直接打开这条视频。"
    : "点一条会跳到 B 站小程序播放，看完点左上角返回就回到这里。";
}
