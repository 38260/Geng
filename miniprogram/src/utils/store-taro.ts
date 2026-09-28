/**
 * favorites.ts 的 Taro 存储适配层。
 *
 * 单独成文件是因为纯逻辑要能被 `node --test` 直接 import 跑单测，
 * 顶层一旦 import @tarojs/taro，在 Node 里就解析不到了。
 */
import Taro from "@tarojs/taro";

import { FAVORITES_KEY, KV } from "./favorites";

export const taroStore: KV = {

  get: (key) => {
    try {
      const value = Taro.getStorageSync(key);
      return typeof value === "string" && value ? value : null;
    } catch {
      return null;
    }
  },
  set: (key, value) => {
    try {
      Taro.setStorageSync(key, value);
    } catch {
      // 存储写不进去（配额满/隐私模式）不该让页面崩掉
    }
  },
  remove: (key) => {
    try {
      Taro.removeStorageSync(key);
    } catch {
      /* 同上 */
    }
  },
};

