/**
 * 收藏逻辑单测：用内存 KV 跑，不需要小程序环境。
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  clearFavorites,
  FAVORITES_KEY,
  favoriteIds,
  isFavorite,
  loadFavorites,
  toggleFavorite,
  type KV,
} from "../src/utils/favorites.ts";

function memory(initial: Record<string, string> = {}): KV & { dump: () => Record<string, string> } {
  const data = { ...initial };
  return {
    get: (key) => (key in data ? data[key] : null),
    set: (key, value) => {
      data[key] = value;
    },
    remove: (key) => {
      delete data[key];
    },
    dump: () => data,
  };
}

const DATE = new Date(2026, 8, 28);

test("空存储与坏数据都不该让收藏页崩", () => {
  assert.deepEqual(loadFavorites(memory()), []);
  assert.deepEqual(loadFavorites(memory({ [FAVORITES_KEY]: "不是 JSON" })), []);
  assert.deepEqual(loadFavorites(memory({ [FAVORITES_KEY]: '{"id":1}' })), [], "不是数组要当空");
  const dirty = `[{"id":1,"name":"甲"},{"name":"缺 id"},{"id":0,"name":"零号"},{"id":"2","name":"字符串 id"}]`;
  assert.deepEqual(
    loadFavorites(memory({ [FAVORITES_KEY]: dirty })),
    [{ id: 1, name: "甲", at: "" }],
    "缺 id / 缺 name / id 不是数字的行都要丢掉",
  );
});

test("收藏与取消收藏", () => {
  const store = memory();
  const added = toggleFavorite(store, { id: 7, name: "闪身步" }, DATE);
  assert.equal(added.added, true);
  assert.deepEqual(added.items, [{ id: 7, name: "闪身步", at: "2026-09-28" }]);
  assert.equal(isFavorite(store, 7), true);
  assert.equal(isFavorite(store, 8), false);

  const removed = toggleFavorite(store, { id: 7, name: "闪身步" }, DATE);
  assert.equal(removed.added, false);
  assert.deepEqual(removed.items, []);
  assert.deepEqual(loadFavorites(store), []);
  assert.equal(FAVORITES_KEY in store.dump(), false, "清空后要删键，不留空数组");
});

test("新收藏排在最前，ids 顺序与列表一致", () => {
  const store = memory();
  toggleFavorite(store, { id: 1, name: "甲" }, DATE);
  toggleFavorite(store, { id: 2, name: "乙" }, new Date(2026, 8, 29));
  assert.deepEqual(favoriteIds(store), [2, 1]);
  clearFavorites(store);
  assert.deepEqual(favoriteIds(store), []);
});
