/**
 * B 站视频链接 → B 站小程序播放页路径。
 *
 * 微信端原来是「复制链接，你自己去浏览器粘贴」，很别扭：小程序之间本来就可以直接跳。
 * 把「链接 → 目标小程序页面」这段纯解析单独拎出来，不依赖 Taro，
 * 这样 `npm test` 能直接测（见 tests/bilibili.test.ts）。
 */

/** 哔哩哔哩小程序 AppID（B 站官方小程序，不是本项目的）。 */
export const BILIBILI_MINIAPP_ID = "wx7564fd5313d24844";

/** B 站小程序播放页路径。 */
const VIDEO_PAGE = "pages/video/video";

/**
 * BV 号：B 站现行格式是 `BV` + 10 位，但库里的演示/测试数据存在 `BV1enc0001` 这类短号，
 * 所以放宽到 8–12 位，别把自家数据判成"解析不出来"。
 *
 * 前面那个 `(?:^|[^0-9A-Za-z])` 是边界：不用 lookbehind——iOS 16.4 以下的
 * JavaScriptCore 不支持，小程序用户的微信版本不能假设那么新。
 */
const BVID_RE = /(?:^|[^0-9A-Za-z])(BV[0-9A-Za-z]{8,12})/;

/** 老式 av 号，部分历史链接还在用。 */
const AVID_RE = /(?:^|[^0-9A-Za-z])av(\d{1,12})/i;

/** 取 BV 号；没有就返回 null。 */
export function parseBvid(url: string): string | null {
  const hit = BVID_RE.exec(String(url || ""));
  return hit ? hit[1] : null;
}

/** 取 av 号；没有就返回 null。 */
export function parseAvid(url: string): string | null {
  const hit = AVID_RE.exec(String(url || ""));
  return hit ? hit[1] : null;
}

/**
 * 交给 `navigateToMiniProgram` 的 path。
 *
 * 解析不出来（空链接 / 演示数据里的假地址 / 非 B 站地址）返回 null，
 * 调用方据此退回「复制链接」——宁可退回复制，也不能点了没反应。
 */
export function bilibiliMiniProgramPath(url: string): string | null {
  const bvid = parseBvid(url);
  if (bvid) return `${VIDEO_PAGE}?bvid=${bvid}`;
  const avid = parseAvid(url);
  if (avid) return `${VIDEO_PAGE}?avid=${avid}`;
  return null;
}
