// 用无头 Edge 截面板的图（自测视觉、README 截图用）。页面有 SSE 长连接，所以按固定等待时间截，不等网络空闲。
// 用法：node scripts/shot.mjs <URL> <输出.png> [--w 1440] [--h 900] [--dark] [--wait 3000] [--click 选择器] [--full]
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const args = process.argv.slice(2);
const url = args[0];
const out = args[1];
const opt = (name, dflt) => {
  const i = args.indexOf(`--${name}`);
  return i === -1 ? dflt : args[i + 1];
};
if (!url || !out) {
  console.error("用法：node scripts/shot.mjs <URL> <输出.png> [--w 1440] [--h 900] [--dark] [--wait 3000] [--click 选择器] [--full]");
  process.exit(2);
}
const width = Number(opt("w", 1440));
const height = Number(opt("h", 900));
const wait = Number(opt("wait", 3000));
const clicks = args.flatMap((a, i) => (a === "--click" ? [args[i + 1]] : []));

const EDGE = process.env.EDGE_PATH || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const port = 9520 + Math.floor(Math.random() * 60);
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "panel-shot-"));
const edge = spawn(EDGE, ["--headless=new", `--remote-debugging-port=${port}`, "--remote-allow-origins=*",
  `--user-data-dir=${profile}`, `--window-size=${width},${height}`, "--hide-scrollbars", "--no-first-run",
  "--no-proxy-server", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

try {
  let target;
  for (let i = 0; i < 40 && !target; i++) {
    await sleep(250);
    try {
      target = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((t) => t.type === "page");
    } catch { /* 还没起来 */ }
  }
  if (!target) throw new Error("Edge 调试端口没起来");
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let id = 0;
  const pending = new Map();
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    }
  };
  const send = (method, params = {}) => new Promise((r) => {
    pending.set(++id, r);
    ws.send(JSON.stringify({ id, method, params }));
  });
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 600 });
  if (args.includes("--dark"))
    await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
  await send("Page.enable");
  await send("Page.navigate", { url });
  await sleep(wait);
  for (const sel of clicks) {
    await send("Runtime.evaluate", { expression: `document.querySelector(${JSON.stringify(sel)})?.click()` });
    await sleep(800);
  }
  const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: args.includes("--full") });
  fs.writeFileSync(out, Buffer.from(shot.result.data, "base64"));
  console.log(`已保存 ${out}（${width}×${height}${args.includes("--dark") ? "，深色" : ""}）`);
  ws.close();
} finally {
  edge.kill();
}
