import { box, C, clamp01, type Ctx, type Pen, text } from "../engine/ink";
import type { Sc } from "../engine/timeline";

export interface Scene {
  id: string;
  draw(ctx: Ctx, s: Sc): void;
}

/** 带标题和小字的方框节点：边先写出来，字随后显现 */
export function node(
  ctx: Ctx, x: number, y: number, w: number, h: number, title: string, sub: string, p: number,
  o: { color?: string; fill?: string; size?: number; seed?: number; align?: "left" | "center" } = {},
): void {
  if (p <= 0) return;
  const pen: Pen = { color: o.color ?? C.ink, width: 2.6, seed: o.seed ?? Math.round(x + y) };
  box(ctx, x, y, w, h, clamp01(p * 1.4), pen, o.fill);
  const center = o.align === "center";
  const tx = center ? x + w / 2 : x + 20;
  const size = o.size ?? 30;
  const pad = sub ? h / 2 - 2 : h / 2 + size * 0.35;
  text(ctx, title, tx, y + pad, { size, p: clamp01(p * 1.6 - 0.4), align: center ? "center" : "left", color: o.color ?? C.ink });
  if (sub) text(ctx, sub, tx, y + h / 2 + size * 0.95, { size: size * 0.62, p: clamp01(p * 1.6 - 0.7), align: center ? "center" : "left", color: C.soft, font: "mono" });
}

/** 小标签（圆角胶囊） */
export function chip(ctx: Ctx, x: number, y: number, s: string, p: number, color = C.ink, fill = "rgba(255,255,255,0.55)", size = 24): number {
  if (p <= 0) return 0;
  ctx.save();
  ctx.font = `400 ${size}px "LXGW WenKai", serif`;
  const w = ctx.measureText(s).width + size * 1.1;
  ctx.restore();
  box(ctx, x, y, w, size * 1.6, clamp01(p * 1.5), { color, width: 2, seed: Math.round(x * 3 + y) }, fill, size * 0.8);
  text(ctx, s, x + size * 0.55, y + size * 1.1, { size, color, p: clamp01(p * 1.5 - 0.3) });
  return w;
}

/** 整章透明度：淡入淡出，外加某一句开始后把旧画面退掉 */
export function fadeOut(s: Sc, line: number, len = 0.6): number {
  return 1 - s.p(line, 0, len);
}
