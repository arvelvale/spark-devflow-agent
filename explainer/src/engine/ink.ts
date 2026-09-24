// 墨线引擎：所有图形都先变成折线，再沿法线加一点手抖，按进度 p（0..1）从头"写"出来。
// 线条每秒换 8 次抖动（3 套轮换），像手绘动画里的"沸腾"，但幅度很小，不晃眼。
import { noise1, rng } from "./random";

export type Pt = [number, number];
export type Ctx = CanvasRenderingContext2D;

export const C = {
  ink: "#2b2925",
  soft: "#77705f",
  faint: "#b3aa96",
  green: "#3b7a4e",
  blue: "#3a61b3",
  amber: "#c0851c",
  red: "#b8433a",
  paperDeep: "#ebe3d1",
  hl: "rgba(248, 208, 72, 0.45)",
  hlGreen: "rgba(122, 190, 132, 0.38)",
  hlBlue: "rgba(122, 162, 232, 0.34)",
  hlRed: "rgba(232, 120, 100, 0.32)",
  hlAmber: "rgba(236, 176, 72, 0.36)",
};

export const FONT = {
  hand: '"LXGW WenKai", "KaiTi", "STKaiti", serif',
  mono: '"LXGW WenKai Mono", "Cascadia Mono", Consolas, monospace',
};

let now = 0;
/** 每帧开始时由播放器设置，用来决定线条的"沸腾"帧 */
export function setInkTime(t: number): void {
  now = t;
}
const boil = () => Math.floor(now * 8) % 3;

export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const easeOut = (x: number) => 1 - Math.pow(1 - clamp01(x), 3);
export const easeInOut = (x: number) => {
  const t = clamp01(x);
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
};
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

export interface Pen {
  color?: string;
  width?: number;
  amp?: number; // 手抖幅度（像素）
  seed?: number;
  alpha?: number;
  dash?: number[];
  still?: boolean; // true = 不沸腾
  double?: boolean; // 叠一道细线，模拟墨水浓淡
}

function resample(pts: Pt[], closed: boolean, step = 6): Pt[] {
  const out: Pt[] = [];
  const n = pts.length, m = closed ? n : n - 1;
  for (let i = 0; i < m; i++) {
    const a = pts[i], b = pts[(i + 1) % n];
    const d = Math.hypot(b[0] - a[0], b[1] - a[1]);
    // 护栏：坐标出现 NaN/Infinity 时 k 会变成无穷大，整页卡死；直接报错把坏数据暴露出来
    if (!Number.isFinite(d) || d > 20000) throw new Error(`墨线坐标异常：(${a}) → (${b})`);
    const k = Math.max(1, Math.ceil(d / step));
    for (let j = 0; j < k; j++) out.push([a[0] + ((b[0] - a[0]) * j) / k, a[1] + ((b[1] - a[1]) * j) / k]);
  }
  if (!closed) out.push(pts[n - 1]);
  else out.push(out[0]);
  return out;
}

function wobble(pts: Pt[], amp: number, seed: number): Pt[] {
  if (amp <= 0 || pts.length < 2) return pts;
  let dist = 0;
  return pts.map((p, i) => {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
    let tx = b[0] - a[0], ty = b[1] - a[1];
    const l = Math.hypot(tx, ty) || 1;
    tx /= l; ty /= l;
    if (i > 0) dist += Math.hypot(p[0] - pts[i - 1][0], p[1] - pts[i - 1][1]);
    const o = (noise1(dist * 0.02, seed) + 0.4 * noise1(dist * 0.07, seed + 7)) * amp;
    return [p[0] - ty * o, p[1] + tx * o];
  });
}

function trace(ctx: Ctx, q: Pt[], p: number): void {
  let total = 0;
  const L = [0];
  for (let i = 1; i < q.length; i++) L.push((total += Math.hypot(q[i][0] - q[i - 1][0], q[i][1] - q[i - 1][1])));
  const target = total * clamp01(p);
  ctx.beginPath();
  ctx.moveTo(q[0][0], q[0][1]);
  for (let i = 1; i < q.length; i++) {
    if (L[i] <= target) ctx.lineTo(q[i][0], q[i][1]);
    else {
      const f = (target - L[i - 1]) / (L[i] - L[i - 1] || 1);
      ctx.lineTo(lerp(q[i - 1][0], q[i][0], f), lerp(q[i - 1][1], q[i][1], f));
      break;
    }
  }
  ctx.stroke();
}

/** 手绘折线；p 是写出来的比例 */
export function stroke(ctx: Ctx, pts: Pt[], p = 1, pen: Pen = {}, closed = false): void {
  if (p <= 0 || pts.length < 2) return;
  const seed = (pen.seed ?? 1) + (pen.still ? 0 : boil() * 101);
  const q = wobble(resample(pts, closed), pen.amp ?? 1.5, seed);
  ctx.save();
  ctx.globalAlpha *= pen.alpha ?? 1;
  ctx.strokeStyle = pen.color ?? C.ink;
  ctx.lineWidth = pen.width ?? 3;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  if (pen.dash) ctx.setLineDash(pen.dash);
  trace(ctx, q, p);
  if (pen.double !== false && (pen.width ?? 3) >= 2.5 && !pen.dash) {
    ctx.globalAlpha *= 0.35;
    ctx.lineWidth = (pen.width ?? 3) * 0.45;
    trace(ctx, wobble(resample(pts, closed), (pen.amp ?? 1.5) * 1.3, seed + 57), p);
  }
  ctx.restore();
}

export function rectPts(x: number, y: number, w: number, h: number, r = 10): Pt[] {
  if (r <= 0) return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
  const pts: Pt[] = [];
  const corner = (cx: number, cy: number, a0: number) => {
    for (let i = 0; i <= 4; i++) {
      const a = a0 + (i / 4) * (Math.PI / 2);
      pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
    }
  };
  corner(x + w - r, y + r, -Math.PI / 2);
  corner(x + w - r, y + h - r, 0);
  corner(x + r, y + h - r, Math.PI / 2);
  corner(x + r, y + r, Math.PI);
  return pts;
}

export function ellipsePts(cx: number, cy: number, rx: number, ry = rx, a0 = -Math.PI / 2, sweep = Math.PI * 2): Pt[] {
  const n = Math.max(16, Math.ceil((Math.max(rx, ry) * sweep) / 14));
  return Array.from({ length: n + 1 }, (_, i) => {
    const a = a0 + (sweep * i) / n;
    return [cx + Math.cos(a) * rx, cy + Math.sin(a) * ry] as Pt;
  });
}

/** 方框：先铺底色（随进度淡入），再写边 */
export function box(ctx: Ctx, x: number, y: number, w: number, h: number, p: number, pen: Pen = {}, fill?: string, r = 12): void {
  if (p <= 0) return;
  if (fill) {
    ctx.save();
    ctx.globalAlpha *= clamp01(p * 1.6);
    ctx.fillStyle = fill;
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, r);
    ctx.fill();
    ctx.restore();
  }
  stroke(ctx, rectPts(x, y, w, h, r), p, pen, true);
}

export function circle(ctx: Ctx, cx: number, cy: number, r: number, p: number, pen: Pen = {}, fill?: string): void {
  if (p <= 0) return;
  if (fill) {
    ctx.save();
    ctx.globalAlpha *= clamp01(p * 1.6);
    ctx.fillStyle = fill;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
  stroke(ctx, ellipsePts(cx, cy, r, r * 0.97, -Math.PI / 2 + 0.3, Math.PI * 2 + 0.25), p, pen);
}

function curvePts(a: Pt, b: Pt, bend: number): Pt[] {
  const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
  const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1;
  const c: Pt = [mx - (dy / l) * bend, my + (dx / l) * bend];
  return Array.from({ length: 25 }, (_, i) => {
    const t = i / 24;
    return [(1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t * t * b[0], (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t * t * b[1]] as Pt;
  });
}

function head(ctx: Ctx, tip: Pt, from: Pt, p: number, pen: Pen): void {
  if (p <= 0) return;
  const a = Math.atan2(tip[1] - from[1], tip[0] - from[0]), s = 14 + (pen.width ?? 3) * 2;
  const l: Pt = [tip[0] - Math.cos(a - 0.45) * s, tip[1] - Math.sin(a - 0.45) * s];
  const r: Pt = [tip[0] - Math.cos(a + 0.45) * s, tip[1] - Math.sin(a + 0.45) * s];
  stroke(ctx, [l, tip, r], p, { ...pen, dash: undefined, amp: 0.6 });
}

/** 箭头：bend 为弧度偏移（像素），先写线身，最后 15% 进度写箭头 */
export function arrow(ctx: Ctx, a: Pt, b: Pt, p: number, pen: Pen = {}, bend = 0): void {
  if (p <= 0) return;
  const pts = bend ? curvePts(a, b, bend) : [a, b];
  stroke(ctx, pts, clamp01(p / 0.85), pen);
  head(ctx, pts[pts.length - 1], pts[pts.length - 2], clamp01((p - 0.85) / 0.15), pen);
}

export function polyArrow(ctx: Ctx, pts: Pt[], p: number, pen: Pen = {}): void {
  if (p <= 0) return;
  stroke(ctx, pts, clamp01(p / 0.88), pen);
  head(ctx, pts[pts.length - 1], pts[pts.length - 2], clamp01((p - 0.88) / 0.12), pen);
}

/** 折线上某个比例位置的点（画移动的小圆点用） */
export function pointAt(pts: Pt[], u: number): Pt {
  const L = [0];
  for (let i = 1; i < pts.length; i++) L.push(L[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  const target = L[L.length - 1] * clamp01(u);
  for (let i = 1; i < pts.length; i++)
    if (L[i] >= target) {
      const f = (target - L[i - 1]) / (L[i] - L[i - 1] || 1);
      return [lerp(pts[i - 1][0], pts[i][0], f), lerp(pts[i - 1][1], pts[i][1], f)];
    }
  return pts[pts.length - 1];
}

export function dot(ctx: Ctx, at: Pt, r: number, color: string, alpha = 1): void {
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(at[0], at[1], r, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

export interface TextOpt {
  size?: number;
  color?: string;
  align?: CanvasTextAlign;
  p?: number; // 从左到右显现的比例
  font?: "hand" | "mono";
  weight?: number;
  alpha?: number;
  baseline?: CanvasTextBaseline;
}

/** 手写字：按进度从左往右露出来，边缘带一点渐隐 */
export function text(ctx: Ctx, s: string, x: number, y: number, o: TextOpt = {}): number {
  const p = o.p ?? 1;
  const size = o.size ?? 36;
  ctx.save();
  ctx.font = `${o.weight ?? 400} ${size}px ${FONT[o.font ?? "hand"]}`;
  ctx.textAlign = o.align ?? "left";
  ctx.textBaseline = o.baseline ?? "alphabetic";
  const w = ctx.measureText(s).width;
  if (p <= 0) {
    ctx.restore();
    return w;
  }
  const left = ctx.textAlign === "center" ? x - w / 2 : ctx.textAlign === "right" ? x - w : x;
  ctx.globalAlpha *= o.alpha ?? 1;
  ctx.fillStyle = o.color ?? C.ink;
  if (p < 1) {
    const edge = left + (w + 40) * p;
    const g = ctx.createLinearGradient(edge - 40, 0, edge, 0);
    g.addColorStop(0, o.color ?? C.ink);
    g.addColorStop(1, "rgba(0,0,0,0)");
    ctx.beginPath();
    ctx.rect(left - 4, y - size * 1.3, edge - left + 4, size * 1.9);
    ctx.clip();
    ctx.fillStyle = g;
    ctx.fillText(s, x, y);
    ctx.fillStyle = o.color ?? C.ink;
    ctx.beginPath();
    ctx.rect(left - 4, y - size * 1.3, Math.max(0, edge - 40 - left + 4), size * 1.9);
    ctx.clip();
  }
  ctx.fillText(s, x, y);
  ctx.restore();
  return w;
}

/** 多行手写：总进度按字数分给每一行 */
export function para(ctx: Ctx, lines: string[], x: number, y: number, lh: number, o: TextOpt = {}): void {
  const total = lines.reduce((a, l) => a + l.length, 0) || 1;
  let acc = 0;
  lines.forEach((l, i) => {
    const p = clamp01(((o.p ?? 1) * total - acc) / (l.length || 1));
    text(ctx, l, x, y + i * lh, { ...o, p });
    acc += l.length;
  });
}

/** 荧光笔：一道粗而半透明的抖线从左划到右 */
export function highlight(ctx: Ctx, x: number, y: number, w: number, h: number, p: number, color = C.hl, seed = 3): void {
  if (p <= 0) return;
  ctx.save();
  ctx.globalCompositeOperation = "multiply";
  stroke(ctx, [[x, y + h / 2], [x + w, y + h / 2 + 2]], p, { color, width: h, amp: 2.2, seed, double: false, still: true });
  ctx.restore();
}

/** 斜线排线填充 */
export function hatch(ctx: Ctx, x: number, y: number, w: number, h: number, p: number, color: string, gap = 11, seed = 5): void {
  if (p <= 0) return;
  ctx.save();
  ctx.beginPath();
  ctx.rect(x, y, w, h);
  ctx.clip();
  const n = Math.ceil((w + h) / gap);
  const shown = Math.floor(n * clamp01(p));
  for (let i = 0; i < shown; i++) {
    const s = i * gap;
    stroke(ctx, [[x + s, y], [x + s - h, y + h]], 1, { color, width: 1.6, amp: 0.6, seed: seed + i, double: false });
  }
  ctx.restore();
}

/** 便利贴：从上方轻轻落下 */
export function note(ctx: Ctx, x: number, y: number, w: number, h: number, p: number, color: string, rot = 0, seed = 11): void {
  if (p <= 0) return;
  const e = easeOut(p);
  ctx.save();
  ctx.translate(x + w / 2, y + h / 2 - (1 - e) * 40);
  ctx.rotate(rot + (1 - e) * 0.15);
  ctx.globalAlpha *= clamp01(p * 2);
  ctx.shadowColor = "rgba(60, 45, 20, 0.18)";
  ctx.shadowBlur = 14;
  ctx.shadowOffsetY = 6;
  ctx.fillStyle = color;
  const r = rng(seed);
  ctx.beginPath();
  ctx.moveTo(-w / 2, -h / 2);
  ctx.lineTo(w / 2, -h / 2 + r() * 3);
  ctx.lineTo(w / 2 - 2, h / 2);
  ctx.quadraticCurveTo(0, h / 2 + 6, -w / 2 + 3, h / 2 - 2);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

/** 印章：放大落下再回弹，双框 */
export function stamp(ctx: Ctx, s: string, x: number, y: number, p: number, color = C.red, rot = -0.08, size = 42): void {
  if (p <= 0) return;
  const t = clamp01(p);
  const scale = t < 0.6 ? lerp(1.7, 0.94, t / 0.6) : lerp(0.94, 1, (t - 0.6) / 0.4);
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rot);
  ctx.scale(scale, scale);
  ctx.globalAlpha *= clamp01(t * 2.2) * 0.9;
  ctx.font = `700 ${size}px ${FONT.hand}`;
  const w = ctx.measureText(s).width + size * 0.9, h = size * 1.5;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = color;
  ctx.fillText(s, 0, 2);
  ctx.restore();
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rot);
  ctx.scale(scale, scale);
  ctx.globalAlpha *= clamp01(t * 2.2) * 0.85;
  stroke(ctx, rectPts(-w / 2, -h / 2, w, h, 6), 1, { color, width: 4, amp: 1.2, seed: 91, still: true }, true);
  stroke(ctx, rectPts(-w / 2 + 7, -h / 2 + 7, w - 14, h - 14, 4), 1, { color, width: 1.5, amp: 1, seed: 92, still: true }, true);
  ctx.restore();
}

export function check(ctx: Ctx, x: number, y: number, s: number, p: number, color = C.green): void {
  stroke(ctx, [[x - s * 0.5, y], [x - s * 0.1, y + s * 0.4], [x + s * 0.6, y - s * 0.5]], p, { color, width: 4.5, amp: 0.8 });
}

export function cross(ctx: Ctx, x: number, y: number, s: number, p: number, color = C.red): void {
  stroke(ctx, [[x - s / 2, y - s / 2], [x + s / 2, y + s / 2]], clamp01(p * 2), { color, width: 5, amp: 0.8 });
  stroke(ctx, [[x + s / 2, y - s / 2], [x - s / 2, y + s / 2]], clamp01(p * 2 - 1), { color, width: 5, amp: 0.8, seed: 9 });
}

/** 横向条形：外框 + 排线填到 frac */
export function bar(ctx: Ctx, x: number, y: number, w: number, h: number, frac: number, p: number, color: string, seed = 21): void {
  box(ctx, x, y, w, h, clamp01(p * 3), { color: C.soft, width: 1.8, seed, amp: 1 }, undefined, 6);
  const fw = w * clamp01(frac) * easeOut(p);
  if (fw > 1) {
    ctx.save();
    ctx.globalAlpha *= 0.85;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.roundRect(x + 3, y + 3, Math.max(0, fw - 6), h - 6, 4);
    ctx.fill();
    ctx.restore();
  }
}
