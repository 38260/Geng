/**
 * 精选推荐挑选规则：与 Web 端 Home.pickFeatured 保持一致，
 * 两端不能挑出不一样的"精选"。
 */
import assert from "node:assert/strict";
import test from "node:test";

import type { MemeCard } from "../src/types/api.ts";
import { pickFeatured } from "../src/utils/featured.ts";

function card(id: number, stage: string, hotness: number, name = `梗${id}`): MemeCard {
  return { id, name, hotness, stage, catch_status: "can_catch" } as unknown as MemeCard;
}

test("每个阶段只挑一个最能打的", () => {
  const picked = pickFeatured([
    card(1, "explosive", 81),
    card(2, "explosive", 70),
    card(3, "rising", 60),
    card(4, "plateau", 40),
    card(5, "sprouting", 12),
  ]);
  assert.deepEqual(picked.map((row) => row.id), [1, 3, 4, 5]);
});

test("阶段不全时用榜单前面的补满 4 个", () => {
  const picked = pickFeatured([card(1, "explosive", 81), card(2, "receding", 53), card(3, "obsolete", 44)]);
  assert.equal(picked.length, 3, "总共只有 3 个梗时不该硬凑");
  assert.deepEqual(picked.map((row) => row.id), [1, 2, 3]);
});

test("空列表不炸，且不会重复挑同一个梗", () => {
  assert.deepEqual(pickFeatured([]), []);
  const only = [card(7, "rising", 66), card(7, "rising", 66)];
  const picked = pickFeatured([...only, card(8, "explosive", 90), card(9, "plateau", 30)]);
  assert.equal(new Set(picked.map((row) => row.id)).size, picked.length, "不许出现重复");
});
