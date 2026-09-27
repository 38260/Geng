/**
 * 唯一的网络出口。
 *
 * - 只调用自己的 FastAPI，不直接连 LongCat（Key 永远不进前端）；
 * - 带超时与统一错误对象，页面拿到的是可渲染的错误态而不是 undefined；
 * - 数字一律在这里做一次"非有限值 → null"清洗，杜绝 NaN。
 */

import type {
  LLMTestResult,
  MemeDetail,
  MemeList,
  Meta,
  SaveLLMResult,
  SettingsView,
  Trend,
  VideoItem,
  InsightRecord,
} from "@/types/api";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";
const TIMEOUT_MS = 15000;

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail || `请求失败（${status}）`);
    this.status = status;
    this.detail = detail;
  }
}

function sanitize<T>(value: T): T {
  if (typeof value === "number") {
    return (Number.isFinite(value) ? value : null) as unknown as T;
  }
  if (Array.isArray(value)) {
    return value.map(sanitize) as unknown as T;
  }
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      out[key] = sanitize(item);
    }
    return out as T;
  }
  return value;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });

    const text = await response.text();
    let payload: unknown = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        throw new ApiError(response.status, "接口返回了无法解析的内容");
      }
    }

    if (!response.ok) {
      const detail =
        (payload as { detail?: string; error?: string } | null)?.detail ??
        (payload as { error?: string } | null)?.error ??
        `请求失败（${response.status}）`;
      throw new ApiError(response.status, String(detail));
    }
    return sanitize(payload) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if ((error as Error)?.name === "AbortError") {
      throw new ApiError(0, "请求超时，请检查后端是否在 8000 端口运行");
    }
    throw new ApiError(0, "网络不可用，请确认后端服务已启动");
  } finally {
    clearTimeout(timer);
  }
}

const query = (params: Record<string, string | number | boolean | undefined>) => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
};

export const api = {
  meta: () => request<Meta>("/api/meta"),

  memes: (params: { filter?: string; search?: string; sort?: string; limit?: number; offset?: number } = {}) =>
    request<MemeList>(`/api/memes${query(params)}`),

  memeDetail: (id: number) => request<MemeDetail>(`/api/memes/${id}`),

  memeTrend: (id: number, window: number) =>
    request<Trend>(`/api/memes/${id}/trend${query({ window })}`),

  memeVideos: (id: number, limit = 8) =>
    request<{ items: VideoItem[]; total: number }>(`/api/memes/${id}/videos${query({ limit })}`),

  regenerateInsight: (id: number, refresh = true) =>
    request<{ trend_explanation: InsightRecord; catch_up_advice: InsightRecord }>(
      `/api/memes/${id}/insight`,
      { method: "POST", body: JSON.stringify({ refresh }) },
    ),

  llmTest: () => request<LLMTestResult>("/api/llm/test", { method: "POST" }),

  llmModels: () => request<{ models: string[] }>("/api/llm/models"),

  settings: () => request<SettingsView>("/api/settings/llm"),

  saveSettings: (body: {
    provider: string;
    base_url: string;
    model: string;
    temperature: number;
    max_tokens: number;
    api_key?: string;
    persist?: boolean;
  }) =>
    request<SaveLLMResult>("/api/settings/llm", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  recompute: () => request<{ ok: boolean; computed: number; skipped: number }>("/api/jobs/recompute", {
    method: "POST",
  }),
};
