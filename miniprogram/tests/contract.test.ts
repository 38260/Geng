/**
 * 接口契约测试：拿真实后端的返回，逐字段核对小程序类型假设。
 *
 * 小程序端不重算任何东西，字段名或可空性一变，界面就是 undefined 或 NaN。
 * 后端改了形状而没跑这个测试，这里就会红。
 *
 * 跑法：后端起来后 `npm test`（默认 http://127.0.0.1:8010，可用 MCP_API_BASE 覆盖）。
 * 后端没起时每条测试各自 skip 并说明原因——不会静默假通过。
 */
import assert from "node:assert/strict";
import test from "node:test";

const BASE = process.env.MCP_API_BASE || "http://127.0.0.1:8010";

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { signal: AbortSignal.timeout(8000) });
  if (!response.ok) throw new Error(`${path} → ${response.status}`);
  return (await response.json()) as T;
}

async function reachable(): Promise<boolean> {
  try {
    return (await get<{ status: string }>("/api/health")).status === "ok";
  } catch {
    return false;
  }
}

/** 后端不在线就 skip（并打印原因），在线就返回 true 继续跑。 */
async function guard(t: { skip: (message?: string) => void }): Promise<boolean> {
  if (await reachable()) return true;
  t.skip(`后端没起（${BASE}），契约测试跳过`);
  return false;
}

test("meta：小程序首页/口径页要用的字段都在", async (t) => {
  if (!(await guard(t))) return;
  const meta = await get<Record<string, any>>("/api/meta");
  for (const key of [
    "app_name", "version", "data_source", "is_demo", "data_through", "data_lag_days",
    "certified_count", "library_count", "gated_out", "candidate_count", "window_days",
    "filters", "lifecycle_stages", "transparency",
  ]) {
    assert.ok(key in meta, `meta 少了 ${key}`);
  }
  for (const key of ["certification_rule", "board_gate", "hotness_algorithm", "lifecycle_algorithm", "sampling", "llm_role"]) {
    assert.ok(key in meta.transparency, `transparency 少了 ${key}`);
  }
  assert.equal(typeof meta.certified_count, "number");
  assert.ok(Array.isArray(meta.filters) && meta.filters.length >= 1);
  // 口径页要显示"上次什么时候刷的、自动刷新开没开"
  assert.ok(meta.refresh && "last" in meta.refresh && "schedule" in meta.refresh, "meta 少了 refresh");
  assert.equal(typeof meta.refresh.schedule.enabled, "boolean");
});

test("榜单：scope=board 与 scope=all 的分母关系成立", async (t) => {
  if (!(await guard(t))) return;
  const board = await get<any>("/api/memes?scope=board&limit=5");
  const all = await get<any>("/api/memes?scope=all&limit=1");
  assert.equal(board.scope, "board");
  assert.ok(board.total <= all.total, `热榜 ${board.total} 不该大于梗库 ${all.total}`);
  assert.equal(board.gated_out, all.total - board.total, "被挡数量应等于两者之差");
});

test("卡片：界面直接渲染的字段不可为空", async (t) => {
  if (!(await guard(t))) return;
  const list = await get<any>("/api/memes?scope=board&limit=10");
  assert.ok(list.items.length, "榜单为空，无法核对字段");
  for (const row of list.items) {
    for (const key of ["id", "name", "hotness", "stage", "stage_label", "nickname", "catch_status", "catch_label", "cert_label", "verification_state", "meme_data_source"]) {
      assert.ok(row[key] !== undefined && row[key] !== null && row[key] !== "", `${row.name} 少了 ${key}`);
    }
    // insufficient 不是结论而是闸门：观测天数不够时算法拒绝判"来不来得及"
    assert.ok(["can_catch", "caution", "too_late", "insufficient"].includes(row.catch_status));
    assert.ok(["双 UP 认证", "梗百科认证", "梗指南认证", "未认证"].includes(row.cert_label));
    assert.ok(row.hotness >= 0 && row.hotness <= 100);
    assert.ok(row.thumbnail && typeof row.thumbnail.emoji === "string");
    // 增长百分比是几天观测出来的，界面必须能查到——不然分不清真跌和接口抖动
    assert.ok("observed_days" in row && "coverage" in row, `${row.name} 少了覆盖度字段`);
    if (row.stage === "insufficient") {
      assert.equal(row.catch_status, "insufficient", "数据不足时不许给赶梗结论");
      assert.equal(row.catch_confidence, 0, "闸门态的置信度必须是 0（算法没给）");
    }
  }
});

test("趋势点要分得清「没观测到」和「真的是 0」", async (t) => {
  if (!(await guard(t))) return;
  const list = await get<any>("/api/memes?scope=board&limit=1");
  const detail = await get<any>(`/api/memes/${list.items[0].id}`);
  for (const point of detail.trend.points) {
    assert.ok(typeof point.observed === "boolean", `${point.date} 少了 observed`);
    if (point.observed === false) {
      assert.equal(point.video_count, 0, "没观测到的日子不该有样本");
    }
  }
  assert.ok("observed_days" in detail.trend && "coverage" in detail.trend, "趋势块少了覆盖度");
});

test("详情：介绍块必须有 text + source，且不许空白", async (t) => {
  if (!(await guard(t))) return;
  const list = await get<any>("/api/memes?scope=board&limit=1");
  const detail = await get<any>(`/api/memes/${list.items[0].id}`);
  for (const key of ["meme", "hotness", "lifecycle", "metrics", "certification", "intro", "videos", "trend", "insight"]) {
    assert.ok(key in detail, `详情少了 ${key}`);
  }
  assert.ok(["manual", "evidence", "none"].includes(detail.intro.source));
  assert.ok(String(detail.intro.text).trim().length > 0, `${detail.meme.name} 的详情页是空白介绍`);
  assert.ok(Array.isArray(detail.intro.evidence));
  assert.equal(Object.keys(detail.hotness.weights).length, 5, "热度五因子");
  assert.ok(Math.abs(Object.values<number>(detail.hotness.weights).reduce((a, b) => a + b, 0) - 1) < 1e-6);
  // 六个真阶段 + 一个「数据不足」闸门态，且当前只有一个
  assert.equal(detail.lifecycle.stages.length, 7);
  assert.equal(detail.lifecycle.stages.filter((s: any) => s.active).length, 1);
});

test("趋势与视频：窗口只接受 7/30，视频带相关性分", async (t) => {
  if (!(await guard(t))) return;
  const list = await get<any>("/api/memes?scope=board&limit=1");
  const id = list.items[0].id;
  const trend = await get<any>(`/api/memes/${id}/trend?window=7`);
  assert.equal(trend.points.length, 7);
  for (const point of trend.points) {
    assert.equal(typeof point.hotness, "number");
    assert.ok(!Number.isNaN(point.hotness));
    assert.equal(typeof point.view, "number");
  }
  const bad = await fetch(`${BASE}/api/memes/${id}/trend?window=9`);
  assert.equal(bad.status, 400, "非法窗口应 400");
  const videos = await get<any>(`/api/memes/${id}/videos?limit=3`);
  for (const video of videos.items) {
    assert.ok(video.relevance_score >= 0.5, `${video.title} 没到相关性阈值却进了采信列表`);
    assert.ok(video.view_text && video.duration_text, "视频卡要用的格式化字段不能缺");
    // 视频行要能跳、要有封面：真实投稿必须有可打开的地址与图床封面
    if (video.data_source === "bilibili") {
      assert.ok(/^https:\/\/www\.bilibili\.com\/video\/BV\w+/.test(video.url), `${video.title} 的跳转地址不对：${video.url}`);
      assert.ok(/^https:\/\/i\d\.hdslb\.com\//.test(video.cover), `${video.title} 没有真实封面：${video.cover}`);
    }
  }
});

test("整库扫一遍：任何一条详情都不该有空白介绍", async (t) => {
  if (!(await guard(t))) return;
  const list = await get<any>("/api/memes?scope=all&limit=100");
  const blank: string[] = [];
  for (const row of list.items) {
    const detail = await get<any>(`/api/memes/${row.id}`);
    if (!String(detail.intro.text || "").trim()) blank.push(row.name);
  }
  assert.deepEqual(blank, [], `这些梗的详情页没有介绍：${blank.join("、")}`);
});
