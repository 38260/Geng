/**
 * 小程序侧的接口层。
 *
 * 三条约定：
 * 1. 只读。小程序不调 /api/manage、/api/jobs 这类写接口——那些是后台维护用的，
 *    V1 也没鉴权，放进小程序等于把改数据的口子暴露到公网。
 * 2. 地址可覆盖。默认打本机 8010（开发者工具勾了"不校验合法域名"才能连通）；
 *    真机调试时在「口径」页把地址改成本机局域网 IP，存进 storage 即可，不用重新编译。
 * 3. 失败要说人话。网络错误、域名没白名单、后端没起，是三种不同的提示，
 *    不能都糊成"加载失败"。
 */
import Taro from "@tarojs/taro";

import type { Meta, MemeDetail, MemeList, Trend, VideoList } from "@/types/api";

/** 默认后端：本机起的 FastAPI（start.bat 用 8000，联调小程序时另起 8010 也行） */
export const DEFAULT_API_BASE = "http://127.0.0.1:8010";

const BASE_STORAGE_KEY = "api_base";

export function apiBase(): string {
  try {
    const saved = Taro.getStorageSync(BASE_STORAGE_KEY);
    if (typeof saved === "string" && saved.trim()) return saved.trim().replace(/\/+$/, "");
  } catch {
    // storage 读不到就用默认值，不该因此让页面打不开
  }
  return DEFAULT_API_BASE;
}

export function setApiBase(base: string): void {
  const value = (base || "").trim().replace(/\/+$/, "");
  if (!value || value === DEFAULT_API_BASE) {
    Taro.removeStorageSync(BASE_STORAGE_KEY);
    return;
  }
  Taro.setStorageSync(BASE_STORAGE_KEY, value);
}

export class ApiError extends Error {
  /** domain = 域名没白名单；offline = 连不上；http = 后端返回了错误码 */
  kind: "domain" | "offline" | "http";
  status?: number;

  constructor(kind: ApiError["kind"], message: string, status?: number) {
    super(message);
    this.kind = kind;
    this.status = status;
  }
}

/** 把微信那串没人看的 errMsg 翻译成能照着排查的话。 */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.kind === "domain") {
      return `连不上 ${apiBase()}：真机访问要把后端换成 https 且在小程序后台配合法域名；开发者工具里可以勾「不校验合法域名」。`;
    }
    if (error.kind === "offline") {
      return `连不上后端（${apiBase()}）。确认服务已启动、手机和电脑在同一网络，或在「口径」页改地址。`;
    }
    return error.message;
  }
  return (error as Error)?.message || "加载失败";
}

function classify(raw: { errMsg?: string; statusCode?: number }, url: string): ApiError {
  const message = String(raw.errMsg || "");
  if (message.includes("url not in domain list") || message.includes("invalid url")) {
    return new ApiError("domain", `域名未白名单：${url}`, 0);
  }
  if (message) {
    return new ApiError("offline", `请求失败：${message}`, 0);
  }
  return new ApiError("http", `接口返回 ${raw.statusCode}`, raw.statusCode);
}

export async function request<T>(path: string, query?: Record<string, string | number | undefined>): Promise<T> {
  const cleaned = Object.entries(query || {}).filter(
    ([, value]) => value !== undefined && value !== "" ,
  );
  const search = cleaned.length
    ? `?${cleaned.map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`).join("&")}`
    : "";
  const url = `${apiBase()}${path}${search}`;

  // 不给 Taro.request 传泛型：它的类型参数要求满足 string|Object|ArrayBuffer 约束，
  // 而我们这里的 T 是页面自己声明的响应形状，直接断言更省事也更不容易误约束。
  let response;
  try {
    response = await Taro.request({ url, timeout: 12000, method: "GET" });
  } catch (error) {
    const detail = (error as { errMsg?: string }) || {};
    throw classify({ errMsg: detail.errMsg || (error as Error)?.message }, url);
  }
  if (response.statusCode >= 400) {
    throw classify({ statusCode: response.statusCode }, url);
  }
  return response.data as T;
}

/* ------------------------- 页面要用的几个只读接口 ------------------------- */

export interface ListParams {
  filter?: string;
  search?: string;
  sort?: string;
  scope?: "board" | "all";
  limit?: number;
  offset?: number;
}

export const getMeta = () => request<Meta>("/api/meta");

export const listMemes = (params: ListParams = {}) => request<MemeList>("/api/memes", { ...params });

export const getDetail = (id: number) => request<MemeDetail>(`/api/memes/${id}`);

export const getTrend = (id: number, window: number) =>
  request<Trend>(`/api/memes/${id}/trend`, { window });

export const getVideos = (id: number, limit = 20, offset = 0) =>
  request<VideoList>(`/api/memes/${id}/videos`, { limit, offset });
