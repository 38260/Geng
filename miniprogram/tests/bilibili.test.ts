/**
 * 「链接 → B 站小程序播放页」的解析单测。
 *
 * 这段解析决定了点击视频到底能不能跳过去：解析对了跳 B 站小程序，
 * 解析不出就退回复制链接。所以这里要把真实链、短号、老 av 号、假地址都钉住。
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  BILIBILI_MINIAPP_ID,
  bilibiliMiniProgramPath,
  parseAvid,
  parseBvid,
} from "../src/utils/bilibili.ts";

test("parseBvid：真实链接取到 BV 号", () => {
  assert.equal(parseBvid("https://www.bilibili.com/video/BV17Eap6GEeW"), "BV17Eap6GEeW");
  assert.equal(parseBvid("https://www.bilibili.com/video/BV15vhR6dEEG/"), "BV15vhR6dEEG");
});

test("parseBvid：带 ?p= 参数、http、无协议都能认", () => {
  assert.equal(parseBvid("https://www.bilibili.com/video/BV1mtY164EUu?p=2&t=10"), "BV1mtY164EUu");
  assert.equal(parseBvid("http://b23.tv/BV1ubh26ZEsb"), "BV1ubh26ZEsb");
  assert.equal(parseBvid("bilibili.com/video/BV1ysME67Em9"), "BV1ysME67Em9");
});

test("parseBvid：库里演示数据的短号也要认（BV + 8 位）", () => {
  assert.equal(parseBvid("https://www.bilibili.com/video/BV1enc0001"), "BV1enc0001");
});

test("parseBvid：没有 BV 号就返回 null，别瞎猜", () => {
  assert.equal(parseBvid(""), null);
  assert.equal(parseBvid("https://example.com/watch?v=123"), null);
  assert.equal(parseBvid("https://www.bilibili.com/video/"), null);
  // 长度不够（BV + 7 位）不算数，避免把随便一段文字当视频号
  assert.equal(parseBvid("https://example.com/BV1234567"), null);
});

test("parseAvid：老式 av 号仍能取到", () => {
  assert.equal(parseAvid("https://www.bilibili.com/video/av200376800"), "200376800");
  assert.equal(parseAvid("https://www.bilibili.com/video/BV17Eap6GEeW"), null);
});

test("bilibiliMiniProgramPath：BV 优先，其次 av，解析不出返回 null", () => {
  assert.equal(
    bilibiliMiniProgramPath("https://www.bilibili.com/video/BV17Eap6GEeW?p=1"),
    "pages/video/video?bvid=BV17Eap6GEeW",
  );
  assert.equal(
    bilibiliMiniProgramPath("https://www.bilibili.com/video/av200376800"),
    "pages/video/video?avid=200376800",
  );
  assert.equal(bilibiliMiniProgramPath(""), null);
  assert.equal(bilibiliMiniProgramPath("https://example.com/video/BVx"), null);
});

test("跳转目标 appId 是哔哩哔哩小程序，且与 app.config.ts 声明的一致", () => {
  // app.config.ts 里的 navigateToMiniProgramAppIdList 引用的就是这一个常量，
  // 这里把值钉住：改了这里就必须同步改微信后台/审核材料里的说明。
  assert.equal(BILIBILI_MINIAPP_ID, "wx7564fd5313d24844");
});
