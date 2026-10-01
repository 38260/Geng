// 真实移动端视口截图（CDP + Emulation.setDeviceMetricsOverride）。
//
// 为什么不用 `chrome --window-size=390,844`：那只是把桌面窗口压窄，
// 页面里的 <meta viewport> 不生效，浏览器仍按桌面规则排版，右侧会被裁掉。
// 只有走 CDP 的 device metrics 覆盖（mobile: true + deviceScaleFactor）才是真手机视口。
//
// 用法（需先用 --remote-debugging-port 起一个 headless Chrome）：
//   node scripts/mobile_shot.mjs <url> <cssWidth> <cssHeight> <out.jpg> [port]
//
// 注意：Git Bash 里要带 MSYS_NO_PATHCONV=1，否则以 "/" 开头的参数会被改写成 Windows 路径。

const [url, wArg, hArg, outPath, portArg] = process.argv.slice(2);
if (!url || !outPath) {
  console.error("用法: node scripts/mobile_shot.mjs <url> <cssWidth> <cssHeight> <out.jpg> [port]");
  process.exit(2);
}
const PORT = Number(portArg || process.env.CDP_PORT || 9333);
const W = Number(wArg || 390);
const H = Number(hArg || 1014);
const DPR = Number(process.env.CDP_DPR || 2);

const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
const target = list.find((t) => t.type === "page");
if (!target) throw new Error(`:${PORT} 上没有 page target，Chrome 是不是没带 --remote-debugging-port？`);

const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

let id = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (!m.id || !pending.has(m.id)) return;
  const p = pending.get(m.id);
  pending.delete(m.id);
  m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result);
};
const send = (method, params = {}) =>
  new Promise((res, rej) => {
    const i = ++id;
    pending.set(i, { res, rej });
    ws.send(JSON.stringify({ id: i, method, params }));
  });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await send("Page.enable");
await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", {
  width: W,
  height: H,
  deviceScaleFactor: DPR,
  mobile: true,
  screenOrientation: { type: "portraitPrimary", angle: 0 },
});
await send("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 5 });

await send("Page.navigate", { url });
await sleep(Number(process.env.CDP_WAIT || 3800)); // 等接口数据 + 图表渲染

// 顺手体检：横向溢出说明窄屏真的排版失败，不是截图姿势问题
const probe = await send("Runtime.evaluate", {
  expression: `(() => {
    const de = document.documentElement;
    return JSON.stringify({
      clientWidth: de.clientWidth,
      scrollWidth: de.scrollWidth,
      scrollHeight: de.scrollHeight,
      overflowX: de.scrollWidth - de.clientWidth,
    });
  })()`,
  returnByValue: true,
});
const info = JSON.parse(probe.result.value);
console.log(
  `[mobile_shot] ${W}x${H}@${DPR}x  client=${info.clientWidth} scrollW=${info.scrollWidth} ` +
  `scrollH=${info.scrollHeight} 横向溢出=${info.overflowX}px`,
);
if (info.overflowX > 0) console.log("  ⚠️ 存在页面级横向溢出，请检查窄屏排版");

const shot = await send("Page.captureScreenshot", { format: "jpeg", quality: 90 });
const fs = await import("node:fs");
fs.writeFileSync(outPath, Buffer.from(shot.data, "base64"));
const kb = (fs.statSync(outPath).size / 1024).toFixed(0);
console.log(`  已存 ${outPath}  ${W * DPR}x${H * DPR}  ${kb} KB`);
ws.close();
process.exit(0);
