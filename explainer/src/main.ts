// 播放器：配音是主时钟，画面每帧按配音的当前时间重画（所以拖进度条、倍速都不会错位）。
//   ?clean      隐藏控件（录屏用）
//   #gate       直接跳到某一章
//   window.__render(t)  按指定时间画一帧（逐帧导出视频用）
import "lxgw-wenkai-webfont/lxgwwenkai-regular.css";
import "lxgw-wenkai-webfont/lxgwwenkai-bold.css";
import "lxgw-wenkai-webfont/lxgwwenkaimono-regular.css";
import "./styles.css";
import { C, FONT, setInkTime, text } from "./engine/ink";
import { makePaper } from "./engine/paper";
import { estimate, locate, type Manifest } from "./engine/timeline";
import { part1 } from "./scenes/part1";
import { part2 } from "./scenes/part2";
import { part3 } from "./scenes/part3";
import script from "./script.json";
import src1 from "./scenes/part1.ts?raw";
import src2 from "./scenes/part2.ts?raw";
import src3 from "./scenes/part3.ts?raw";

const W = 1920, H = 1080;
const SCENES = [...part1, ...part2, ...part3];
const $ = <T extends HTMLElement>(s: string) => document.querySelector(s) as T;

const canvas = $<HTMLCanvasElement>("#stage");
const ctx = canvas.getContext("2d")!;
const audio = new Audio();
audio.preload = "auto";
let manifest: Manifest = estimate(script);
let hasAudio = false;
let paper: HTMLCanvasElement;
let captions = true;
let playing = false;
let silentT = 0, silentAt = 0; // 没有配音时用的时钟

function now(): number {
  if (hasAudio) return audio.currentTime;
  return playing ? silentT + ((performance.now() - silentAt) / 1000) * audio.playbackRate : silentT;
}

function seek(t: number): void {
  t = Math.max(0, Math.min(manifest.total - 0.01, t));
  if (hasAudio) audio.currentTime = t;
  silentT = t;
  silentAt = performance.now();
}

function resize(): void {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const r = canvas.getBoundingClientRect();
  canvas.width = Math.round(r.width * dpr);
  canvas.height = Math.round(r.height * dpr);
}

function drawChrome(index: number, title: string, alpha: number): void {
  ctx.save();
  ctx.globalAlpha = alpha;
  text(ctx, `${String(index + 1).padStart(2, "0")}`, 110, 110, { size: 30, font: "mono", color: C.green });
  text(ctx, title, 170, 110, { size: 34, color: C.soft });
  ctx.restore();
  // 右上：章节点
  manifest.scenes.forEach((_, i) => {
    ctx.beginPath();
    ctx.arc(1810 - (manifest.scenes.length - 1 - i) * 22, 100, i === index ? 7 : 4, 0, Math.PI * 2);
    ctx.fillStyle = i <= index ? C.green : C.faint;
    ctx.fill();
  });
}

/** 字幕：超过 1640 宽时在最靠近中间的标点处折成两行 */
function drawCaption(s: string): void {
  ctx.save();
  ctx.font = `400 36px ${FONT.hand}`;
  let lines = [s];
  if (ctx.measureText(s).width > 1640) {
    const mid = s.length / 2;
    let cut = -1;
    [...s].forEach((ch, i) => { if ("，；：、".includes(ch) && (cut < 0 || Math.abs(i - mid) < Math.abs(cut - mid))) cut = i; });
    if (cut < 0) cut = Math.floor(mid) - 1;
    lines = [s.slice(0, cut + 1), s.slice(cut + 1)];
  }
  const w = Math.max(...lines.map((l) => ctx.measureText(l).width)) + 80;
  const h = 64 + (lines.length - 1) * 50;
  ctx.fillStyle = "rgba(243, 236, 221, 0.9)";
  ctx.beginPath();
  ctx.roundRect(960 - w / 2, 1040 - h, w, h, 10);
  ctx.fill();
  ctx.restore();
  lines.forEach((l, i) => text(ctx, l, 960, 1084 - h + i * 50, { size: 36, align: "center", color: C.ink }));
}

function render(t: number): void {
  setInkTime(t);
  const sx = canvas.width / W, sy = canvas.height / H;
  ctx.setTransform(sx, 0, 0, sy, 0, 0);
  ctx.drawImage(paper, 0, 0, W, H);
  const { index, sc, line } = locate(manifest, t);
  const scene = SCENES.find((x) => x.id === sc.scene.id);
  ctx.save();
  ctx.globalAlpha = sc.alpha;
  scene?.draw(ctx, sc);
  ctx.restore();
  drawChrome(index, sc.scene.title, Math.min(1, sc.t / 0.4));
  if (captions && line) drawCaption(line.text);
}

// ---------------- 控件 ----------------
const playBtn = $<HTMLButtonElement>("#play");
const scrub = $<HTMLInputElement>("#scrub");
const timeEl = $("#time");
const chapters = $("#chapters");
const ticks = $("#ticks");
const cover = $("#cover");

const fmt = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;

function setPlaying(v: boolean): void {
  playing = v;
  if (hasAudio) {
    if (v) void audio.play().catch(() => (playing = false));
    else audio.pause();
  } else {
    silentT = now();
    silentAt = performance.now();
  }
  playBtn.textContent = v ? "暂停" : "播放";
  playBtn.setAttribute("aria-label", v ? "暂停" : "播放");
  document.body.classList.toggle("playing", v);
}

function buildChapters(): void {
  chapters.replaceChildren();
  ticks.replaceChildren();
  manifest.scenes.forEach((s, i) => {
    const b = document.createElement("button");
    b.innerHTML = `<span>${String(i + 1).padStart(2, "0")}</span>${s.title}`;
    b.onclick = () => { seek(s.start + 0.01); if (!playing) setPlaying(true); };
    chapters.append(b);
    const tk = document.createElement("i");
    tk.style.left = `${(s.start / manifest.total) * 100}%`;
    tk.title = s.title;
    ticks.append(tk);
  });
  scrub.max = String(manifest.total);
}

function syncUi(t: number): void {
  scrub.value = String(t);
  timeEl.textContent = `${fmt(t)} / ${fmt(manifest.total)}`;
  const { index } = locate(manifest, t);
  [...chapters.children].forEach((c, i) => c.classList.toggle("on", i === index));
}

playBtn.onclick = () => setPlaying(!playing);
scrub.oninput = () => seek(+scrub.value);
$("#cc").onclick = (e) => { captions = !captions; (e.currentTarget as HTMLElement).classList.toggle("off", !captions); };
$("#speed").onclick = (e) => {
  const rates = [1, 1.25, 1.5, 0.75];
  const next = rates[(rates.indexOf(audio.playbackRate) + 1) % rates.length];
  silentT = now(); silentAt = performance.now();
  audio.playbackRate = next;
  (e.currentTarget as HTMLElement).textContent = `${next}×`;
};
$("#full").onclick = () => {
  const el = $(".player");
  if (document.fullscreenElement) void document.exitFullscreen();
  else void el.requestFullscreen?.().catch(() => undefined);
};
$("#start").onclick = () => { cover.hidden = true; setPlaying(true); };
audio.onended = () => setPlaying(false);
window.addEventListener("keydown", (e) => {
  if (e.target instanceof HTMLInputElement && e.target.type !== "range") return;
  const { index } = locate(manifest, now());
  if (e.key === " ") { e.preventDefault(); cover.hidden = true; setPlaying(!playing); }
  else if (e.key === "ArrowRight") seek(manifest.scenes[Math.min(index + 1, manifest.scenes.length - 1)].start + 0.01);
  else if (e.key === "ArrowLeft") seek(manifest.scenes[Math.max(index - 1, 0)].start + 0.01);
  else if (e.key.toLowerCase() === "c") $("#cc").click();
});
window.addEventListener("resize", resize);

// ---------------- 启动 ----------------
async function boot(): Promise<void> {
  if (new URLSearchParams(location.search).has("clean")) document.body.classList.add("clean");
  resize();
  paper = makePaper(W, H);
  try {
    const r = await fetch("audio/manifest.json");
    if (r.ok) {
      manifest = await r.json();
      audio.src = "audio/narration.mp3";
      hasAudio = true;
    }
  } catch { /* 没有配音就按字数估时长、静音播放 */ }
  $("#voice").textContent = hasAudio ? `配音：阶跃 stepaudio-2.5-tts · ${manifest.voice ?? ""}` : "未生成配音（npm run tts），静音播放";
  buildChapters();
  // 预载画面和字幕里用到的字（字体按字切片，不预载会先闪一下回退字体）
  const chars = [...new Set(script.scenes.flatMap((s) => [s.title, ...s.lines]).join("") + src1 + src2 + src3)].join("");
  await Promise.all([
    document.fonts.load(`400 40px "LXGW WenKai"`, chars),
    document.fonts.load(`700 40px "LXGW WenKai"`, chars),
    document.fonts.load(`400 40px "LXGW WenKai Mono"`, chars),
  ]).catch(() => undefined);
  const hash = location.hash.slice(1);
  const target = manifest.scenes.find((s) => s.id === hash);
  if (target) seek(target.start + 0.01);
  $("#loading").hidden = true;
  const loop = () => {
    const t = now();
    if (!hasAudio && playing && t >= manifest.total) setPlaying(false);
    render(t);
    syncUi(t);
    requestAnimationFrame(loop);
  };
  loop();
}

(window as unknown as { __render: (t: number) => void; __total: () => number }).__render = (t) => render(t);
/** 导出用：按 1920×1080 原始分辨率画一帧并返回 dataURL */
(window as unknown as { __frame: (t: number, type: string) => string }).__frame = (t, type) => {
  if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
  render(t);
  return canvas.toDataURL(type, 0.92);
};
(window as unknown as { __total: () => number }).__total = () => manifest.total;
void boot();
