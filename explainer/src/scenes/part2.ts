// 第 5–8 章：JEV 决策层、本地为主、写操作门控、上下文与记忆
import {
  arrow, bar, box, C, circle, clamp01, dot, easeOut, ellipsePts, highlight, lerp, rectPts, stamp, stroke, text,
  type Ctx, type Pt,
} from "../engine/ink";
import { rng } from "../engine/random";
import { chip, fadeOut, node, type Scene } from "./common";

/** 半圆仪表：Noul 的"是/否程度" */
function gauge(ctx: Ctx, cx: number, cy: number, r: number, v: number, p: number): void {
  stroke(ctx, ellipsePts(cx, cy, r, r, Math.PI, Math.PI), p, { width: 3, seed: 5 });
  for (let i = 0; i <= 4; i++) {
    const a = Math.PI + (i / 4) * Math.PI;
    stroke(ctx, [[cx + Math.cos(a) * (r - 14), cy + Math.sin(a) * (r - 14)], [cx + Math.cos(a) * r, cy + Math.sin(a) * r]], p, { width: 2, seed: 6 + i, double: false });
  }
  const a = Math.PI + clamp01(v * easeOut(p)) * Math.PI;
  stroke(ctx, [[cx, cy], [cx + Math.cos(a) * (r - 22), cy + Math.sin(a) * (r - 22)]], p, { color: C.red, width: 4, seed: 12 });
  dot(ctx, [cx, cy], 7 * clamp01(p * 2), C.ink);
}

const jev: Scene = {
  id: "jev",
  draw(ctx, s) {
    // 第一句：JEV 的三种题型
    const a0 = fadeOut(s, 1, 0.6);
    if (a0 > 0) {
      ctx.save();
      ctx.globalAlpha *= a0;
      const p = s.p(0, 0.1, 1);
      node(ctx, 760, 200, 400, 120, "JEV", "只做选择和打分", p, { align: "center", size: 48, fill: "rgba(255,255,255,0.55)" });
      const q = (f: number) => s.at(0, f, 0.9);
      text(ctx, "Noul · 是否", 360, 470, { size: 32, p: q(0.35), align: "center" });
      gauge(ctx, 360, 640, 120, 0.87, q(0.35));
      text(ctx, "0.87", 360, 690, { size: 30, p: q(0.4), align: "center", font: "mono" });
      text(ctx, "Choice · 选哪个", 960, 470, { size: 32, p: q(0.5), align: "center" });
      [0.72, 0.21, 0.07].forEach((v, i) => bar(ctx, 810, 510 + i * 56, 300, 38, v, q(0.5 + i * 0.05), i ? C.faint : C.green, 30 + i));
      text(ctx, "Score · 几级", 1560, 470, { size: 32, p: q(0.62), align: "center" });
      for (let i = 0; i < 5; i++) box(ctx, 1400 + i * 66, 540, 56, 56, q(0.62), { width: 2.4, seed: 40 + i }, i === 3 ? "rgba(122,190,132,0.45)" : undefined, 8);
      text(ctx, "丢弃 · 摘要 · 保留", 1560, 650, { size: 26, p: q(0.7), align: "center", color: C.soft });
      // "不写文字"：一支被划掉的笔
      const np = q(0.12);
      stroke(ctx, [[1230, 250], [1330, 190]], np, { width: 5, seed: 50 });
      stroke(ctx, [[1330, 190], [1344, 183]], np, { width: 5, seed: 51, color: C.soft });
      stroke(ctx, [[1220, 180], [1350, 270]], q(0.2), { width: 4, color: C.red, seed: 52 });
      text(ctx, "不写文字", 1360, 250, { size: 28, p: q(0.2), color: C.red });
      text(ctx, "给出来的是概率", 960, 830, { size: 38, p: q(0.8), align: "center" });
      highlight(ctx, 820, 810, 280, 30, q(0.85), C.hl);
      ctx.restore();
    }
    // 第二句：两级漏斗 + 三道门控
    const L1 = s.L(1) > 0;
    if (L1) {
      const skills = ["issue-breakdown", "plan-writer", "implement-change", "progress-logger", "status-sync", "standup-brief", "review-gate", "meeting-to-tasks"];
      const tp = s.at(1, 0.05, 0.9);
      skills.forEach((k, i) => chip(ctx, 110 + (i % 4) * 205, 180 + Math.floor(i / 4) * 56, k.split("-")[0], clamp01(tp * 2 - i * 0.1), C.soft, "rgba(255,255,255,0.5)", 20));
      const fp = s.at(1, 0.2, 1);
      stroke(ctx, [[100, 300], [920, 300], [640, 470], [380, 470], [100, 300]], fp, { width: 2.6, seed: 60, color: C.soft }, false);
      text(ctx, "第一级：全部技能粗排", 510, 400, { size: 28, align: "center", p: fp });
      const f2 = s.at(1, 0.55, 1);
      ["standup", "progress", "status"].forEach((k, i) => chip(ctx, 330 + i * 130, 490, k, f2, C.ink, "rgba(255,255,255,0.6)", 20));
      stroke(ctx, [[320, 550], [720, 550], [600, 680], [440, 680], [320, 550]], f2, { width: 2.6, seed: 61, color: C.soft });
      text(ctx, "第二级：前三名逐个问", 520, 625, { size: 26, align: "center", p: f2 });
      // 门控三问
      const g = s.at(1, 0.35, 1.2);
      text(ctx, "三道门控题", 1080, 210, { size: 32, p: g });
      [["要动仓库/任务", 0.7], ["有既定流程", 0.84], ["光说就够（反向）", 0.12]].forEach(([n, v], i) => {
        text(ctx, n as string, 1080, 280 + i * 64, { size: 26, p: g, color: C.soft });
        bar(ctx, 1320, 254 + i * 64, 400, 34, v as number, clamp01(g * 1.3 - i * 0.15), C.faint, 70 + i);
      });
      const gv = s.at(1, 0.55, 1);
      text(ctx, "门控值 0.81", 1080, 500, { size: 30, p: gv });
      bar(ctx, 1320, 474, 400, 34, 0.81, gv, C.green, 80);
      stroke(ctx, [[1320 + 400 * 0.3, 462], [1320 + 400 * 0.3, 520]], gv, { color: C.red, width: 3, seed: 81 });
      text(ctx, "阈值 0.30", 1330, 546, { size: 22, p: gv, color: C.red });
    }
    // 第三句：真实例子
    if (s.L(2) > 0) {
      const cp = s.p(2, 0, 0.9);
      box(ctx, 1040, 590, 760, 300, cp, { width: 2.6, seed: 90 }, "rgba(255,255,255,0.6)", 10);
      text(ctx, "「最近 3 条提交是什么」", 1070, 642, { size: 32, p: cp });
      const bp = s.at(2, 0.25, 1);
      [["none", 0.55], ["standup-brief", 0.31], ["progress-logger", 0.13]].forEach(([n, v], i) => {
        text(ctx, n as string, 1070, 706 + i * 50, { size: 22, p: bp, font: "mono" });
        bar(ctx, 1300, 684 + i * 50, 300, 30, v as number, bp, i ? C.faint : C.amber, 100 + i);
      });
      stroke(ctx, [[1450, 672], [1450, 830]], bp, { color: C.red, width: 2.6, seed: 104, dash: [6, 6] });
      text(ctx, "0.50", 1456, 856, { size: 20, p: bp, color: C.red, font: "mono" });
      stamp(ctx, "不用技能", 1700, 720, s.at(2, 0.6, 0.7), C.green, -0.12, 34);
      text(ctx, "不去硬凑", 1640, 820, { size: 28, p: s.at(2, 0.8, 0.8), color: C.green });
    }
  },
};

const router: Scene = {
  id: "router",
  draw(ctx, s) {
    // 第一句：MoE —— 30 个专家，每个 token 只点亮 3 个
    const gp = s.p(0, 0.1, 1.2);
    text(ctx, "Nemotron-3.5 · 300 亿参数", 110, 200, { size: 36, p: gp });
    const r = rng(7);
    const lit = Array.from({ length: 40 }, () => [0, 1, 2].map(() => Math.floor(r() * 30)));
    const tok = Math.floor(Math.max(0, s.L(0) - 1.5) * 2.2);
    for (let i = 0; i < 30; i++) {
      const x = 380 + (i % 10) * 54, y = 250 + Math.floor(i / 10) * 54;
      const on = tok > 0 && s.L(1) < 0 && lit[tok % lit.length].includes(i);
      box(ctx, x, y, 42, 42, clamp01(gp * 2 - i * 0.03), { width: 1.8, seed: 200 + i, color: on ? C.green : C.faint }, on ? "rgba(122,190,132,0.7)" : undefined, 6);
    }
    if (tok > 0) {
      const u = (s.L(0) * 2.2) % 1;
      dot(ctx, [lerp(200, 380, u), 331], 10, C.amber, s.L(1) < 0 ? 1 : 0.3);
      dot(ctx, [lerp(930, 1030, u), 331], 10, C.amber, s.L(1) < 0 ? 1 : 0.3);
    }
    text(ctx, "token", 200, 290, { size: 24, p: gp, font: "mono", color: C.amber });
    text(ctx, "每个 token 只激活 30 亿", 1040, 300, { size: 32, p: s.at(0, 0.45) });
    const fp = s.at(0, 0.75);
    for (let i = 0; i < 4; i++) box(ctx, 1040 + i * 30, 340, 24, 24, fp, { width: 1.8, seed: 300 + i, color: C.blue }, i < 2 ? "rgba(122,162,232,0.6)" : undefined, 3);
    text(ctx, "NVFP4 · GB10 原生精度", 1170, 362, { size: 30, p: fp, color: C.blue });
    // 第二句：赛跑
    const rp = s.lin(1, 0.2, 3);
    text(ctx, "同一节点生成速度", 110, 560, { size: 30, p: s.p(1, 0, 0.8), color: C.soft });
    const lanes = [["Nemotron · vLLM", 80, C.green], ["Qwen · Ollama", 12, C.soft]] as const;
    lanes.forEach(([n, v, col], i) => {
      const y = 600 + i * 90;
      text(ctx, n, 110, y + 42, { size: 28, p: s.p(1, 0, 0.8) });
      bar(ctx, 360, y + 10, 480, 44, (v / 80) * easeOut(rp), s.p(1, 0, 0.6), col, 400 + i);
      text(ctx, `${Math.round(v * easeOut(rp))} tok/s`, 860, y + 44, { size: 30, p: s.p(1, 0.2, 0.6), font: "mono", color: col });
    });
    stamp(ctx, "×6–7", 740, 540, s.at(1, 0.75, 0.6), C.green, -0.1, 36);
    // 第三句：岔路
    const fk = s.p(2, 0, 1.2);
    const o: Pt = [1180, 700];
    stroke(ctx, [[1010, 700], o], fk, { width: 4, seed: 500 });
    arrow(ctx, o, [1560, 560], s.at(2, 0.1, 0.9), { color: C.green, width: 4, seed: 501 }, -30);
    arrow(ctx, o, [1560, 840], s.at(2, 0.35, 0.9), { color: C.blue, width: 4, seed: 502 }, 30);
    node(ctx, 1570, 510, 270, 100, "本地 Nemotron", "日常步骤", s.at(2, 0.15), { color: C.green, fill: "rgba(122,190,132,0.18)" });
    node(ctx, 1570, 790, 270, 100, "云端 step-5", "要写代码 且 不简单", s.at(2, 0.45), { color: C.blue, fill: "rgba(122,162,232,0.16)" });
    text(ctx, "JEV 判难度", 1060, 660, { size: 28, p: fk, color: C.soft });
    chip(ctx, 1060, 880, "修 DAY-298：要写代码 0.96 → 上云", s.at(2, 0.75), C.blue, "rgba(122,162,232,0.12)", 24);
  },
};

// 门控真实标定点：in_scope, collateral, 期望放行？
const PTS: [number, number, boolean, string][] = [
  [0.79, 0.04, true, "跑测试"], [0.49, 0.14, true, "改 store.py"], [0.78, 0.08, true, "写测试"], [0.73, 0.35, true, "提交"],
  [0.83, 0.04, true, "建分支"], [0.03, 0.82, false, "删 README 说明"], [0.03, 0.72, false, "覆盖 AGENTS.md"],
  [0.07, 0.95, false, "改版本号"], [0.58, 0.4, false, "提交写 update"],
];
// 旧的单问题版本：同样 9 次调用的得分
const OLD: [number, boolean][] = [[0.42, true], [0.16, true], [0.53, true], [0.56, true], [0.72, true], [0.02, false], [0.02, false], [0.02, false], [0.17, false]];

const gate: Scene = {
  id: "gate",
  draw(ctx, s) {
    // 第一句：一道闸口、一个问题
    const q = s.p(0, 0.1, 1);
    box(ctx, 110, 200, 800, 130, q, { width: 2.8, seed: 3 }, "rgba(255,255,255,0.55)", 12);
    text(ctx, "问 JEV：", 140, 250, { size: 30, p: q, color: C.soft });
    text(ctx, "「这次调用合不合理？」", 140, 305, { size: 44, p: s.p(0, 0.5, 1.2) });
    const gp = s.at(0, 0.6) * fadeOut(s, 2, 0.5);
    stroke(ctx, [[1000, 330], [1000, 180]], gp, { width: 5, seed: 7 });
    stroke(ctx, [[1000, 190], [1180, 250]], gp, { width: 5, seed: 8, color: C.amber });
    stroke(ctx, [[960, 330], [1060, 330]], gp, { width: 5, seed: 9 });
    // 第二句：一条数轴，两堆点挤在一起
    const lp = s.p(1, 0, 1);
    const X = (v: number) => 140 + v * 740, Y = 560;
    stroke(ctx, [[X(0), Y], [X(1), Y]], lp, { width: 3, seed: 20 });
    [0, 0.5, 1].forEach((v) => text(ctx, v.toFixed(1), X(v), Y + 40, { size: 22, align: "center", p: lp, font: "mono", color: C.soft }));
    OLD.forEach(([v, ok], i) => {
      const p = s.at(1, 0.08 + i * 0.05, 0.6);
      if (p <= 0) return;
      const y = lerp(Y - 140, Y - 16 - (i % 3) * 20, easeOut(p));
      dot(ctx, [X(v), y], 11, ok ? C.green : C.red, clamp01(p * 2));
    });
    const ov = s.at(1, 0.6, 0.9);
    highlight(ctx, X(0.1), Y - 90, X(0.24) - X(0.1), 110, ov, C.hlRed, 8);
    text(ctx, "合法最低 0.16 · 越界最高 0.17", 140, 680, { size: 32, p: ov });
    text(ctx, "分不开", 140, 740, { size: 44, p: s.at(1, 0.78, 0.8), color: C.red, weight: 700 });
    text(ctx, "绿 = 合法调用　红 = 越界调用", 140, 420, { size: 24, p: lp, color: C.soft });
    // 第三句：两个问题 → 平面分开
    const pp = s.p(2, 0, 1);
    const PX = (v: number) => 1080 + v * 680, PY = (v: number) => 860 - v * 620;
    if (pp > 0) {
      ctx.save();
      ctx.globalAlpha *= clamp01(pp * 1.5) * 0.9;
      ctx.fillStyle = "rgba(122,190,132,0.22)";
      ctx.fillRect(PX(0.5), PY(0.5), PX(1) - PX(0.5), PY(0) - PY(0.5));
      ctx.fillStyle = "rgba(236,176,72,0.18)";
      ctx.fillRect(PX(0), PY(1), PX(1) - PX(0), PY(0.5) - PY(1));
      ctx.restore();
    }
    stroke(ctx, [[PX(0), PY(1)], [PX(0), PY(0)], [PX(1), PY(0)]], pp, { width: 3, seed: 30 });
    stroke(ctx, [[PX(0.5), PY(0)], [PX(0.5), PY(0.5)], [PX(1), PY(0.5)]], pp, { width: 2, seed: 31, dash: [8, 8], color: C.soft });
    stroke(ctx, [[PX(0), PY(0.5)], [PX(0.5), PY(0.5)]], pp, { width: 2, seed: 32, dash: [8, 8], color: C.soft });
    text(ctx, "是不是合理步骤 →", PX(1), PY(0) + 44, { size: 26, align: "right", p: pp });
    text(ctx, "↑ 会不会删改无关内容", PX(0), PY(1) - 18, { size: 26, p: pp });
    text(ctx, "放行", PX(0.75), PY(0.25) + 10, { size: 30, align: "center", p: pp, color: C.green });
    text(ctx, "问你", PX(0.82), PY(0.9), { size: 30, align: "center", p: pp, color: C.amber });
    PTS.forEach(([x, y, ok], i) => {
      const p = s.at(2, 0.15 + i * 0.035, 0.5);
      if (p <= 0) return;
      dot(ctx, [PX(x), PY(y)], 11, ok ? C.green : C.red, clamp01(p * 2));
    });
    // 三个破坏性改动被圈出并盖章
    PTS.slice(5, 8).forEach(([x, y], i) => circle(ctx, PX(x), PY(y), 24, s.at(2, 0.55 + i * 0.06, 0.5), { color: C.red, width: 3, seed: 40 + i }));
    stamp(ctx, "全部拦下", PX(0.36), PY(0.68), s.at(2, 0.72, 0.6), C.red, -0.1, 34);
    text(ctx, "9 条标定 · 7 条符合 · 样本还少", 1080, 950, { size: 24, p: s.at(2, 0.85, 0.8), color: C.soft });
  },
};

const context: Scene = {
  id: "context",
  draw(ctx, s) {
    // 第一句：卡片越堆越高，越过水位线；工作记忆被钉住
    const base = 860, ch = 74, x0 = 130, w = 420;
    const grow = s.lin(0, 0.2, s.lineDur(0) * 0.55);
    const shown = Math.min(7, Math.floor(grow * 7.99));
    const L1 = s.L(1);
    const verdict = ["留摘要", "丢弃", "保留"];
    const cards = Array.from({ length: 7 }, (_, i) => i);
    const archived = (i: number) => (i === 1 ? s.at(1, 0.55, 0.9) : 0);
    const folded = (i: number) => (i === 0 ? s.at(1, 0.45, 0.8) : 0);
    let y = base;
    cards.forEach((i) => {
      if (i >= shown) return;
      const fold = folded(i), arc = archived(i);
      const h = lerp(ch, 26, fold) * (1 - easeOut(arc));
      if (h < 1) return;
      y -= h + 8;
      const dx = easeOut(arc) * 440;
      box(ctx, x0 + dx, y, w, h, 1, { width: 2.2, seed: 100 + i, color: fold > 0.5 ? C.blue : C.ink }, fold > 0.5 ? "rgba(122,162,232,0.2)" : "rgba(255,255,255,0.6)", 8);
      if (fold < 0.5) {
        text(ctx, `第 ${i + 1} 轮`, x0 + 20 + dx, y + h / 2 + 10, { size: 26, alpha: 1 - fold * 2 });
        stroke(ctx, [[x0 + 150 + dx, y + h / 2], [x0 + 380 + dx, y + h / 2]], 1 - fold * 2, { color: C.faint, width: 3, seed: 110 + i, double: false });
      } else text(ctx, "第 1 轮摘要 · 150 字", x0 + 20, y + 20, { size: 18, color: C.blue });
      if (i < 3 && L1 > 0) stamp(ctx, verdict[i], x0 + w - 70 + dx, y + h / 2, s.at(1, 0.08 + i * 0.1, 0.5), [C.blue, C.red, C.green][i], -0.12, 22);
    });
    const wl = base - (ch + 8) * 5.6; // 7 张卡越过水位线；压缩后（5 张 + 摘要条）落到线下
    stroke(ctx, [[100, wl], [600, wl]], s.p(0, 0.2, 1), { color: C.amber, width: 3, seed: 150, dash: [12, 8] });
    text(ctx, "预算 70%", 610, wl + 8, { size: 26, p: s.p(0, 0.2, 1), color: C.amber });
    const pin = s.at(0, 0.6, 1);
    box(ctx, 700, 190, 400, 220, pin, { width: 2.6, seed: 160, color: C.green }, "rgba(122,190,132,0.16)", 10);
    circle(ctx, 900, 196, 12, pin, { color: C.red, width: 2 }, C.red);
    ["目标", "约束", "待办", "关键证据"].forEach((t, i) => text(ctx, `· ${t}`, 730 + (i % 2) * 180, 270 + Math.floor(i / 2) * 60, { size: 30, p: clamp01(pin * 1.5 - i * 0.12) }));
    text(ctx, "工作记忆 · 永远不压缩", 720, 450, { size: 26, p: s.at(0, 0.8), color: C.green });
    // 第二句：存档抽屉
    const dp = s.at(1, 0.4, 0.8);
    box(ctx, 580, 640, 420, 170, dp, { width: 2.6, seed: 170, color: C.soft }, "rgba(235,227,209,0.8)", 8);
    stroke(ctx, [[740, 700], [840, 700]], dp, { width: 3, seed: 171 });
    text(ctx, "archive.jsonl", 790, 760, { size: 24, align: "center", p: dp, font: "mono", color: C.soft });
    text(ctx, "原文可取回", 790, 850, { size: 28, align: "center", p: s.at(1, 0.75), color: C.soft });
    // 第三句：长期记忆
    const mp = s.p(2, 0, 1);
    text(ctx, "长期记忆", 1180, 200, { size: 38, p: mp });
    text(ctx, "金额 · 按分 · 存整数", 1180, 290, { size: 34, p: s.at(2, 0.05) });
    const lens = s.at(2, 0.12);
    circle(ctx, 1300, 278, 70, lens, { width: 3, seed: 180 });
    stroke(ctx, [[1350, 328], [1400, 378]], lens, { width: 6, seed: 181 });
    text(ctx, "关键词召回", 1420, 390, { size: 26, p: lens, color: C.soft });
    [["金额统一按分存整数", 0.83, "原文", C.green], ["CSV 导出要带 BOM", 0.52, "一行", C.amber], ["会议在周三", 0.21, "丢弃", C.faint]].forEach(([t, v, place, col], i) => {
      const p = s.at(2, 0.3 + i * 0.12, 0.8);
      text(ctx, t as string, 1180, 480 + i * 80, { size: 28, p });
      bar(ctx, 1480, 454 + i * 80, 200, 34, v as number, p, col as string, 190 + i);
      text(ctx, `${place}`, 1700, 480 + i * 80, { size: 26, p, color: col as string });
    });
    text(ctx, "JEV 判相关度", 1480, 440, { size: 22, p: s.at(2, 0.3), color: C.soft });
    const lk = s.at(2, 0.72);
    box(ctx, 1200, 760, 46, 40, lk, { width: 2.6, seed: 199 }, "rgba(184,67,58,0.15)", 6);
    stroke(ctx, ellipsePts(1223, 760, 14, 16, Math.PI, Math.PI), lk, { width: 2.6, seed: 198 });
    text(ctx, "隐私内容从不离开节点", 1270, 792, { size: 32, p: lk, color: C.red });
    void rectPts; void arrow;
  },
};

export const part2: Scene[] = [jev, router, gate, context];
