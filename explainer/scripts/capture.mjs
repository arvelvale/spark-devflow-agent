// 用无头 Edge 按时间点渲染画面（页面暴露了 window.__render(t)，画面只由时间决定）。
//   node scripts/capture.mjs stills out/ 12.5,30,61        指定时间点截静帧
//   node scripts/capture.mjs scenes out/                    每章各截两帧（章中、章末）自检用
//   node scripts/capture.mjs video out/explainer.mp4 [fps]  逐帧导出并合上配音（默认 30fps）
// 需要先 npm run build && npm run preview（默认 http://127.0.0.1:4174）
import { spawn, execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const [mode, out, arg] = process.argv.slice(2);
const URL_ = process.env.URL || "http://127.0.0.1:4174/?clean";
const EDGE = process.env.EDGE_PATH || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
if (!mode || !out) {
  console.error("用法：node scripts/capture.mjs stills|scenes|video <输出> [参数]");
  process.exit(2);
}
const port = 9600 + Math.floor(Math.random() * 60);
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "explainer-cap-"));
const edge = spawn(EDGE, ["--headless=new", `--remote-debugging-port=${port}`, "--remote-allow-origins=*", `--user-data-dir=${profile}`,
  "--window-size=1920,1080", "--hide-scrollbars", "--no-first-run", "--no-proxy-server", "--mute-audio", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (m) => process.env.QUIET || console.error(`[capture] ${m}`);

try {
  let target;
  for (let i = 0; i < 40 && !target; i++) {
    await sleep(250);
    try { target = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((t) => t.type === "page"); } catch { /* 未就绪 */ }
  }
  if (!target) throw new Error("Edge 调试端口没起来");
  log("Edge 已就绪");
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let id = 0;
  const pending = new Map();
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  const send = (method, params = {}) => new Promise((r) => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
  const evaluate = async (expr) => {
    const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.result?.exceptionDetails) throw new Error(`页面报错：${r.result.exceptionDetails.exception?.description ?? r.result.exceptionDetails.text}`);
    return r.result?.result?.value;
  };
  await send("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
  await send("Page.enable");
  await send("Page.navigate", { url: URL_ });
  log("页面加载中");
  for (let i = 0; i < 60; i++) { await sleep(250); if (await evaluate("document.getElementById('loading')?.hidden === true")) break; }
  log("页面就绪");
  await sleep(600);
  // 停掉页面自己的动画循环，改为按我们给的时间画
  await evaluate("window.requestAnimationFrame = () => 0; true");
  await sleep(100);
  // 直接从画布取像素：不依赖合成器出帧（停掉页面动画循环后 captureScreenshot 会一直等下一帧）
  const shot = async (t, file) => {
    const type = file.endsWith(".png") ? "image/png" : "image/jpeg";
    // 一帧 PNG 有 6 MB（纸纹噪点多），CDP 单条消息太大时 Node 的 WebSocket 会静默卡住，所以分块取回
    const len = await evaluate(`(window.__buf = window.__frame(${t}, "${type}")).length`);
    const CHUNK = 1 << 20;
    let url = "";
    for (let off = 0; off < len; off += CHUNK) url += await evaluate(`window.__buf.slice(${off}, ${off + CHUNK})`);
    fs.writeFileSync(file, Buffer.from(url.slice(url.indexOf(",") + 1), "base64"));
  };
  if (mode === "probe") {
    for (const expr of ["1+1", "typeof window.__frame", "window.__render(0); 'r0'", "window.__render(50); 'r50'", "window.__render(58); 'r58'", "window.__render(60); 'r60'", "window.__frame(0,'image/png').length"]) {
      log(`试 ${expr}`);
      log(`→ ${await evaluate(expr)}`);
    }
  } else if (mode === "stills" || mode === "scenes") {
    fs.mkdirSync(out, { recursive: true });
    let times;
    if (mode === "stills") times = arg.split(",").map(Number);
    else {
      const m = JSON.parse(fs.readFileSync(path.resolve("public/audio/manifest.json"), "utf8"));
      times = m.scenes.flatMap((s) => [(s.start + s.end) / 2, s.end - 1.25]);
    }
    for (const t of times) {
      const f = path.join(out, `t${t.toFixed(1).padStart(6, "0")}.png`);
      await shot(t, f);
      console.log(`已保存 ${f}`);
    }
  } else if (mode === "video") {
    const fps = Number(arg || 30);
    const total = await evaluate("window.__total()");
    const frames = fs.mkdtempSync(path.join(os.tmpdir(), "explainer-frames-"));
    const n = Math.ceil(total * fps);
    for (let i = 0; i < n; i++) {
      await shot(i / fps, path.join(frames, `f${String(i).padStart(6, "0")}.jpg`));
      if (i % (fps * 10) === 0) console.log(`  ${(i / fps).toFixed(0)}s / ${total.toFixed(0)}s`);
    }
    execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-framerate", String(fps), "-i", path.join(frames, "f%06d.jpg"),
      "-i", path.resolve("public/audio/narration.mp3"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "128k", "-shortest", out]);
    fs.rmSync(frames, { recursive: true, force: true });
    console.log(`已导出 ${out}`);
  }
  ws.close();
} finally {
  edge.kill();
}
