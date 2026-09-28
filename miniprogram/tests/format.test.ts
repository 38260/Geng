/**
 * 展示层纯函数单测：`npm test` 用 Node 自带的 test runner + TS 类型剥离，
 * 不引 jest/vitest，小程序包体和依赖都越少越好。
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  catchTone,
  compact,
  confidenceText,
  dateCn,
  dayShort,
  freshnessText,
  growthText,
  introTone,
  isRealMeme,
  isStale,
  isUp,
  normalizeSeries,
  stageTone,
} from "../src/utils/format.ts";

test("compact：万/亿 与千分位", () => {
  assert.equal(compact(999), "999");
  assert.equal(compact(12_345), "1.2万");
  assert.equal(compact(178_100_000), "1.8亿");
  assert.equal(compact(null), "0");
});

test("growthText：没有对照说 —，不拿 0 冒充没涨", () => {
  assert.equal(growthText(null), "—");
  assert.equal(growthText(undefined), "—");
  assert.equal(growthText(NaN), "—");
  assert.equal(growthText(23616), "+23,616%");
  assert.equal(growthText(-40), "-40%");
  assert.equal(growthText(0), "0%");
  assert.equal(isUp(0), false);
  assert.equal(isUp(3), true);
});

test("日期：空值给「未知」，不给空白", () => {
  assert.equal(dateCn(null), "未知");
  assert.equal(dateCn("2026-09-26T00:00:00"), "9 月 26 日");
  assert.equal(dayShort("2026-09-26"), "09-26");
});

test("freshnessText：滞后超过一天要标出来", () => {
  assert.equal(freshnessText("2026-09-28", 0), "统计截至 9 月 28 日（含今天）");
  assert.equal(freshnessText("2026-09-27", 1), "统计截至 9 月 27 日（昨天）");
  assert.equal(freshnessText("2026-09-25", 3), "统计截至 9 月 25 日 · 已滞后 3 天");
  assert.equal(isStale(3), true);
  assert.equal(isStale(1), false);
  assert.equal(isStale(null), false);
  assert.equal(freshnessText(null, null), "还没有采集数据");
});

test("配色映射不能漏阶段，否则界面会拿到 undefined", () => {
  // insufficient 是闸门态，界面同样要拿到配色，不能漏
  for (const stage of ["sprouting", "rising", "explosive", "plateau", "receding", "obsolete", "insufficient"]) {
    assert.ok(stageTone(stage as never).chip, stage);
  }
  for (const status of ["can_catch", "caution", "too_late", "insufficient"]) {
    assert.ok(catchTone(status as never).chip, status);
  }
  assert.ok(introTone("evidence"));
  assert.ok(introTone("none"));
});

test("真实与演示要分得开", () => {
  assert.equal(isRealMeme("bilibili", "verified_both"), true);
  assert.equal(isRealMeme("bilibili", "partially_verified"), true);
  assert.equal(isRealMeme("bilibili", "unverified"), false, "没在真实投稿里命中的不算真实数据");
  assert.equal(isRealMeme("mock", "verified_both"), false);
});

test("置信度为 0 表示算法没给，不能显示成 0%", () => {
  assert.equal(confidenceText(0.95), "判断置信度 95%");
  assert.equal(confidenceText(0), "置信度：算法未给出");
});

test("normalizeSeries：全 0 不产生 NaN，峰值归一", () => {
  const flat = normalizeSeries([0, 0, 0]);
  assert.deepEqual(flat, [0.06, 0.06, 0.06]);
  const up = normalizeSeries([10, 20, 40]);
  assert.equal(up[2], 1);
  assert.equal(up[1], 0.5);
});
