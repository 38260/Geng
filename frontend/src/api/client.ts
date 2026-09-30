/**
 * 唯一的网络出口。
 *
 * - 只调用自己的 FastAPI，不直接连 LongCat（Key 永远不进前端）；
 * - 带超时与统一错误对象，页面拿到的是可渲染的错误态而不是 undefined；
 * - 数字一律在这里做一次"非有限值 → null"清洗，杜绝 NaN。
 */

import type {
  LLMTestResult,
  ManageList,
  ManageView,
  MemeDetail,
  MemeList,
  MemeMetaPatch,
  MemeMetaResult,
  Meta,
  PipelineView,
  RefreshStatus,
  SaveLLMResult,
  SettingsView,
  Trend,
  VideoItem,
  InsightRecord,
} from "@/types/api";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";
const TIMEOUT_MS = 15000;
/** AI 文案是慢操作（LLM 可能要 20s），单独放宽，别让它误判成网络故障 */
const AI_TIMEOUT_MS = 45000;

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

async function request<T>(path: string, init?: RequestInit, timeoutMs = TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
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
      const typed = payload as { detail?: string; error?: string } | null;
      // Vite 代理在后端挂掉时回 500 且不带我们的错误结构 —— 说人话
      const looksLikeProxyError =
        response.status === 500 && !typed?.detail && !typed?.error;
      const detail =
        typed?.detail ??
        typed?.error ??
        (looksLikeProxyError
          ? "后端不可达：可能没启动，或端口和 VITE_API_TARGET 不一致"
          : `请求失败（${response.status}）`);
      throw new ApiError(response.status, String(detail));
    }
    return sanitize(payload) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if ((error as Error)?.name === "AbortError") {
      throw new ApiError(0, "请求超时，请确认后端已启动（默认 http://127.0.0.1:8010）");
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

  /* 数据管线：数据获取/处理/建模/质量/AI 五段实况。只读接口，不需要令牌 */
  pipeline: () => request<PipelineView>("/api/pipeline"),

  memes: (params: { filter?: string; search?: string; sort?: string; limit?: number; offset?: number; scope?: "board" | "all" } = {}) =>
    request<MemeList>(`/api/memes${query(params)}`),

  memeDetail: (id: number) => request<MemeDetail>(`/api/memes/${id}`),

  memeTrend: (id: number, window: number) =>
    request<Trend>(`/api/memes/${id}/trend${query({ window })}`),

  memeVideos: (id: number, limit = 8, sort: "rank" | "view" = "rank") =>
    request<{
      items: VideoItem[];
      total: number;
      sort: string;
      /** 实际生效的排法：请求默认排序但库里没名次时会是 view */
      sort_applied: string;
      sort_label: string;
      note: string;
    }>(`/api/memes/${id}/videos${query({ limit, sort })}`),

  regenerateInsight: (id: number, refresh = true) =>
    request<{ trend_explanation: InsightRecord; catch_up_advice: InsightRecord }>(
      `/api/memes/${id}/insight`,
      { method: "POST", body: JSON.stringify({ refresh }) },
      AI_TIMEOUT_MS,
    ),

  llmTest: () => request<LLMTestResult>("/api/llm/test", { method: "POST" }, AI_TIMEOUT_MS),

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

  /* 刷新：慢操作，后端立刻返回 202，前端轮询 refreshStatus */
  refreshNow: (full = false) =>
    request<{ ok: boolean; reason?: string; mode?: string }>(`/api/jobs/refresh?full=${full}`, {
      method: "POST",
    }),

  refreshStatus: () => request<RefreshStatus>("/api/jobs/refresh"),

  /* 梗管理：只改封面 / 介绍 / 别名 / 关键词，改不到算法结论 */
  manageMemes: (params: { search?: string; status?: string } = {}) =>
    request<ManageList>(`/api/manage/memes${query(params)}`),

  manageMeme: (id: number) => request<ManageView>(`/api/manage/memes/${id}`),

  createMeme: (body: { name: string; description?: string; aliases?: string[]; keywords?: string[] }) =>
    request<{ created: boolean; meme: ManageView }>("/api/manage/memes", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  saveMemeMeta: (id: number, body: MemeMetaPatch) =>
    request<MemeMetaResult>(`/api/manage/memes/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
};
