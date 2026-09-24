// 时间线：画面跟配音对齐。每章里的动画按"第几句开始后多少秒"来安排，
// 所以换音色、改台词后重新生成配音，动画会自动跟上新的节奏。
import { clamp01, easeOut } from "./ink";

export interface LineT { text: string; start: number; end: number }
export interface SceneT { id: string; title: string; start: number; end: number; lines: LineT[] }
export interface Manifest { total: number; scenes: SceneT[]; voice?: string }

interface ScriptJson { scenes: { id: string; title: string; lines: string[] }[] }

/** 没有配音时按字数估时长（约每秒 4.3 个字），节奏参数与 scripts/tts.mjs 一致 */
export function estimate(script: ScriptJson): Manifest {
  const LEAD = 0.6, GAP = 0.45, TAIL = 1.1;
  let t = 0;
  const scenes = script.scenes.map((s) => {
    const start = t;
    t += LEAD;
    const lines = s.lines.map((text, i) => {
      if (i) t += GAP;
      const st = t;
      t += Math.max(1.2, text.length / 4.3);
      return { text, start: st, end: t };
    });
    t += TAIL;
    return { id: s.id, title: s.title, start, end: t, lines };
  });
  return { total: t, scenes };
}

/** 交给每个场景的时间视图 */
export class Sc {
  constructor(readonly scene: SceneT, readonly t: number) {}
  get dur(): number { return this.scene.end - this.scene.start; }
  /** 第 i 句开始后过了多少秒（还没开始为负） */
  L(i: number): number {
    const line = this.scene.lines[Math.min(i, this.scene.lines.length - 1)];
    return this.scene.start + this.t - line.start;
  }
  lineDur(i: number): number {
    const line = this.scene.lines[Math.min(i, this.scene.lines.length - 1)];
    return line.end - line.start;
  }
  /** 第 i 句开始后 delay 秒起、持续 len 秒的缓动进度 0..1 */
  p(i: number, delay = 0, len = 1): number {
    return easeOut((this.L(i) - delay) / len);
  }
  /** 线性进度（移动的点用） */
  lin(i: number, delay = 0, len = 1): number {
    return clamp01((this.L(i) - delay) / len);
  }
  /** 第 i 句说到 frac 处的时间点之后的进度（按句子长度的比例安排，跟语速走） */
  at(i: number, frac: number, len = 0.9): number {
    return this.p(i, this.lineDur(i) * frac, len);
  }
  /** 整章淡入淡出 */
  get alpha(): number {
    const inA = clamp01(this.t / 0.45);
    const outA = clamp01((this.dur - this.t) / 0.55);
    return Math.min(inA, outA);
  }
}

export function locate(m: Manifest, t: number): { index: number; sc: Sc; line: LineT | null } {
  let index = m.scenes.findIndex((s) => t < s.end);
  if (index < 0) index = m.scenes.length - 1;
  const scene = m.scenes[index];
  const local = Math.max(0, Math.min(t, scene.end) - scene.start);
  const line = scene.lines.find((l) => t >= l.start && t <= l.end + 0.25) ?? null;
  return { index, sc: new Sc(scene, local), line };
}
