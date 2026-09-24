// 第 1–4 章：开场、它做什么、三块地盘、一轮对话
import {
  arrow, box, C, circle, clamp01, dot, easeOut, highlight, lerp, note, pointAt, polyArrow, rectPts, stroke, text,
  type Ctx, type Pt,
} from "../engine/ink";

import { fadeOut, node, type Scene } from "./common";

/** 被撕开的便利贴：落下（drop）后沿锯齿撕成两半（tear） */
function tornNote(ctx: Ctx, x: number, y: number, w: number, h: number, color: string, rot: number, drop: number, tear: number, label: string, seed: number): void {
  if (drop <= 0) return;
  const halves: [number, (c: Ctx) => void][] = [
    [-1, (c) => { c.moveTo(-w, -h); c.lineTo(-4, -h); zig(c, true); c.lineTo(-w, h); }],
    [1, (c) => { c.moveTo(w, -h); c.lineTo(-4, -h); zig(c, true); c.lineTo(w, h); }],
  ];
  function zig(c: Ctx, _down: boolean) {
    for (let i = 0; i <= 8; i++) c.lineTo((i % 2 ? 7 : -7) - 4, -h + (2 * h * i) / 8);
  }
  const e = easeOut(tear);
  for (const [dir, clip] of halves) {
    ctx.save();
    ctx.translate(x + w / 2 + dir * e * 26, y + h / 2 + e * 14);
    ctx.rotate(rot + dir * e * 0.12);
    ctx.beginPath();
    clip(ctx);
    ctx.closePath();
    ctx.clip();
    ctx.translate(-(x + w / 2), -(y + h / 2));
    note(ctx, x, y, w, h, drop, color, 0, seed);
    text(ctx, label, x + w / 2, y + h / 2 + 14, { size: 40, align: "center", p: clamp01(drop * 1.5 - 0.3) });
    ctx.restore();
  }
}

const intro: Scene = {
  id: "intro",
  draw(ctx, s) {
    const a = fadeOut(s, 2, 0.7);
    ctx.save();
    ctx.globalAlpha *= a;
    // 笔记本电脑
    const lp = s.p(0, 0, 1.2);
    box(ctx, 760, 330, 400, 250, lp, { width: 3, seed: 4 }, "rgba(255,255,255,0.35)", 14);
    stroke(ctx, [[700, 600], [1220, 600], [1180, 640], [740, 640]], lp, { width: 3, seed: 5 }, true);
    for (let i = 0; i < 6; i++) {
      const w = [220, 160, 260, 120, 200, 150][i];
      stroke(ctx, [[800 + (i % 3) * 18, 380 + i * 30], [800 + (i % 3) * 18 + w, 380 + i * 30]], s.p(0, 0.3 + i * 0.12, 0.5), { color: i % 2 ? C.green : C.soft, width: 3, seed: 30 + i });
    }
    // 三张便利贴，跟着"拆计划、写日志、同步状态"落下，句末被撕开
    const tear = s.p(0, s.lineDur(0) - 0.6, 0.8);
    tornNote(ctx, 380, 250, 250, 170, "#f7e08a", -0.08, s.at(0, 0.5), tear, "拆计划", 1);
    tornNote(ctx, 1290, 230, 250, 170, "#f4bcb0", 0.07, s.at(0, 0.66), tear, "写日志", 2);
    tornNote(ctx, 1260, 560, 260, 170, "#b9d3ef", -0.05, s.at(0, 0.82), tear, "同步状态", 3);
    // 第二句：一条墨线把链路串起来，旁边"看得见""量得出"
    const road: Pt[] = [[300, 800], [620, 720], [960, 790], [1300, 710], [1640, 780]];
    polyArrow(ctx, road, s.p(1, 0.3, 2.2), { color: C.green, width: 4, seed: 8 });
    const eye = s.at(1, 0.62);
    stroke(ctx, [[620, 860], [660, 836], [700, 860], [660, 884], [620, 860]], eye, { width: 3, seed: 12 });
    circle(ctx, 660, 860, 9, eye, { width: 3 }, C.ink);
    text(ctx, "看得见", 720, 872, { size: 34, p: eye });
    const ruler = s.at(1, 0.82);
    box(ctx, 1080, 838, 200, 44, ruler, { width: 3, seed: 13 }, "rgba(255,255,255,0.4)", 4);
    for (let i = 1; i < 10; i++) stroke(ctx, [[1080 + i * 20, 838], [1080 + i * 20, 838 + (i % 5 ? 12 : 22)]], ruler, { width: 2, seed: 40 + i, double: false });
    text(ctx, "量得出", 1300, 872, { size: 34, p: ruler });
    ctx.restore();
    // 第三句：标题
    const tp = s.p(2, 0.2, 1.4);
    ctx.save();
    ctx.globalAlpha *= clamp01(s.L(2) / 0.4);
    highlight(ctx, 690, 470, 540, 64, s.p(2, 1.1, 0.9), C.hlGreen);
    text(ctx, "Spark 开发流", 960, 520, { size: 104, align: "center", p: tp, weight: 700 });
    text(ctx, "跑在 NVIDIA DGX Spark 上的开发流 agent", 960, 610, { size: 38, align: "center", p: s.p(2, 1.3, 1.4), color: C.soft });
    // GB10 芯片小涂鸦
    const cp = s.p(2, 2.2, 1);
    box(ctx, 900, 670, 120, 120, cp, { width: 3, seed: 61 }, "rgba(255,255,255,0.4)", 10);
    for (let i = 0; i < 4; i++) {
      const o = 690 + i * 26;
      stroke(ctx, [[880, o], [900, o]], cp, { width: 2.5, seed: 70 + i, double: false });
      stroke(ctx, [[1020, o], [1040, o]], cp, { width: 2.5, seed: 80 + i, double: false });
    }
    text(ctx, "GB10", 960, 742, { size: 32, align: "center", p: cp, font: "mono" });
    ctx.restore();
  },
};

const flow: Scene = {
  id: "flow",
  draw(ctx, s) {
    const agent: Pt = [560, 520];
    // 三个来源
    const srcs = [
      { y: 200, f: 0.12, draw: (p: number) => {
        node(ctx, 110, 200, 300, 110, "Linear issue", "DAY-298 金额精度", p, { color: C.blue, fill: "rgba(122,162,232,0.12)" });
      } },
      { y: 420, f: 0.42, draw: (p: number) => {
        stroke(ctx, [[110, 420], [370, 420], [410, 460], [410, 560], [110, 560]], p, { width: 2.6, seed: 17 }, true);
        stroke(ctx, [[370, 420], [370, 460], [410, 460]], p, { width: 2, seed: 18 });
        text(ctx, "Obsidian 纪要", 132, 466, { size: 30, p });
        for (let i = 0; i < 3; i++) stroke(ctx, [[134, 494 + i * 20], [134 + [230, 180, 210][i], 494 + i * 20]], p, { color: C.faint, width: 2.5, seed: 19 + i, double: false });
      } },
      { y: 650, f: 0.7, draw: (p: number) => {
        stroke(ctx, [[120, 650], [400, 650], [400, 740], [200, 740], [160, 778], [168, 740], [120, 740]], p, { width: 2.6, seed: 23 }, true);
        text(ctx, "「把 DAY-298 修掉」", 138, 706, { size: 30, p });
      } },
    ];
    srcs.forEach((src, i) => {
      const p = s.at(0, src.f, 1.1);
      src.draw(p);
      arrow(ctx, [420, src.y + (i === 1 ? 70 : 50)], [agent[0] - 70, agent[1] + (i - 1) * 30], s.at(0, src.f + 0.12, 0.8), { width: 2.6, seed: 90 + i, color: C.soft }, (i - 1) * -30);
    });
    // agent：一个小圆脸
    const ap = s.p(0, 0.2, 1);
    circle(ctx, agent[0], agent[1], 62, ap, { width: 3.5, seed: 7 }, "rgba(122,190,132,0.25)");
    dot(ctx, [agent[0] - 20, agent[1] - 10], 6 * ap, C.ink);
    dot(ctx, [agent[0] + 20, agent[1] - 10], 6 * ap, C.ink);
    stroke(ctx, [[agent[0] - 20, agent[1] + 18], [agent[0], agent[1] + 30], [agent[0] + 20, agent[1] + 18]], ap, { width: 3, seed: 9 });
    text(ctx, "agent", agent[0], agent[1] + 110, { size: 30, align: "center", p: ap, font: "mono" });
    // 第二句：五站链路
    const stations = ["拆解", "计划", "开发", "写日志", "同步状态"];
    const xs = [820, 1060, 1300, 1540, 1760];
    const ys = [430, 610, 430, 610, 430];
    const road: Pt[] = [[agent[0] + 70, agent[1]], ...xs.map((x, i) => [x, ys[i]] as Pt)];
    stroke(ctx, road, s.p(1, 0.2, 2.6), { color: C.faint, width: 5, seed: 31, dash: [2, 14] });
    stations.forEach((name, i) => {
      const p = s.at(1, 0.18 + i * 0.14, 0.8);
      circle(ctx, xs[i], ys[i], 52, p, { width: 3, seed: 40 + i, color: C.green }, "rgba(255,255,255,0.6)");
      text(ctx, name, xs[i], ys[i] + 11, { size: name.length > 3 ? 22 : name.length > 2 ? 26 : 32, align: "center", p });
    });
    const travel = s.lin(1, 1.2, 99);
    if (travel > 0) dot(ctx, pointAt(road, (s.L(1) * 0.12) % 1), 11, C.amber);
    // 第三句：每站落下一张 SKILL.md，右下计数
    stations.forEach((_, i) => {
      const p = s.at(2, 0.1 + i * 0.1, 0.7);
      const x = xs[i] - 50, y = ys[i] + (ys[i] > 500 ? 80 : -170);
      box(ctx, x, y, 100, 76, p, { width: 2, seed: 60 + i, color: C.soft }, "rgba(255,255,255,0.7)", 4);
      text(ctx, "SKILL", x + 50, y + 34, { size: 20, align: "center", p, font: "mono", color: C.green });
      text(ctx, ".md", x + 50, y + 60, { size: 20, align: "center", p, font: "mono", color: C.soft });
    });
    const tally = s.at(2, 0.7, 1.4);
    for (let i = 0; i < 8; i++) {
      const tp = clamp01(tally * 8 - i);
      const x = 1440 + (i < 5 ? i * 22 : 140 + (i - 5) * 22);
      if (i === 4) stroke(ctx, [[1426, 836], [1530, 790]], tp, { width: 4, seed: 77, color: C.red });
      else stroke(ctx, [[x, 790], [x - 4, 840]], tp, { width: 4, seed: 70 + i });
    }
    text(ctx, "8 个技能", 1640, 830, { size: 38, p: s.at(2, 0.85, 0.8) });
  },
};

const arch: Scene = {
  id: "arch",
  draw(ctx, s) {
    const regions: [number, number, number, number, string, number][] = [
      [70, 170, 400, 700, "你的电脑", 0.05],
      [530, 170, 820, 700, "DGX Spark 节点", 0.35],
      [1410, 170, 440, 700, "外部服务", 0.65],
    ];
    regions.forEach(([x, y, w, h, label, f], i) => {
      const p = s.at(0, f, 1.1);
      stroke(ctx, rectPts(x, y, w, h, 18), p, { color: C.soft, width: 2.4, dash: [10, 10], seed: 3 + i }, true);
      text(ctx, label, x + 24, y + 48, { size: 34, p, color: C.soft });
    });
    // 第二句：节点里的东西
    const p1 = (k: number) => s.at(1, 0.05 + k * 0.16, 0.9);
    node(ctx, 110, 290, 320, 100, "浏览器面板", "Vite + TS", p1(0));
    node(ctx, 580, 290, 300, 100, "Web 后端", "server.py · SSE", p1(0));
    arrow(ctx, [430, 340], [580, 340], p1(1), { width: 2.6, seed: 5 });
    node(ctx, 930, 290, 380, 100, "内核 · 一轮 turn", "kernel.py", p1(1), { fill: "rgba(122,190,132,0.16)" });
    arrow(ctx, [880, 340], [930, 340], p1(1), { width: 2.6, seed: 6 });
    node(ctx, 580, 560, 360, 110, "vLLM · Nemotron", "~80 tok/s · 本地主力", p1(2), { color: C.green, fill: "rgba(122,190,132,0.2)" });
    node(ctx, 980, 560, 330, 110, "Ollama · Qwen", "本地备用", p1(3), { color: C.soft });
    arrow(ctx, [1060, 390], [800, 560], p1(2), { color: C.green, width: 3.2, seed: 7 }, 20);
    text(ctx, "本地推理", 870, 470, { size: 30, p: p1(3), color: C.green });
    // 第三句：外部服务 + 隧道
    const p2 = (f: number, len = 0.9) => s.at(2, f, len);
    node(ctx, 1460, 270, 340, 100, "StepFun step-5", "难题 · 语音", p2(0.02), { color: C.blue });
    node(ctx, 1460, 470, 340, 100, "JEV", "api.typesafe.ai", p2(0.08));
    node(ctx, 1460, 650, 340, 100, "Linear", "演示项目", p2(0.12));
    arrow(ctx, [1310, 320], [1460, 320], p2(0.05), { color: C.blue, width: 3, seed: 9 });
    text(ctx, "国内直连", 1318, 300, { size: 24, p: p2(0.1), color: C.blue });
    // 直连 JEV：被叉掉
    const direct = p2(0.2, 0.6);
    arrow(ctx, [1250, 390], [1455, 505], direct, { color: C.soft, width: 2.6, seed: 10, dash: [8, 8] });
    const x = p2(0.3, 0.5);
    if (x > 0) {
      stroke(ctx, [[1330, 420], [1370, 470]], x, { color: C.red, width: 5, seed: 1 });
      stroke(ctx, [[1370, 420], [1330, 470]], clamp01(x * 2 - 0.5), { color: C.red, width: 5, seed: 2 });
      text(ctx, "境外不通", 1300, 510, { size: 26, p: x, color: C.red });
    }
    // 反向隧道：内核 → 你的电脑（本机代理）→ JEV / Linear
    node(ctx, 110, 640, 320, 100, "本机代理", "SSH 反向隧道出口", p2(0.42), { color: C.amber });
    const tunnel: Pt[] = [[1000, 390], [1000, 480], [500, 480], [500, 690], [430, 690]];
    const out1: Pt[] = [[270, 740], [270, 820], [1380, 820], [1380, 520], [1460, 520]];
    const out2: Pt[] = [[1380, 700], [1460, 700]];
    const tp = p2(0.5, 1.4), op = p2(0.66, 1.4);
    polyArrow(ctx, tunnel, tp, { color: C.amber, width: 3.4, seed: 11, dash: [12, 9] });
    polyArrow(ctx, out1, op, { color: C.amber, width: 3.4, seed: 12, dash: [12, 9] });
    arrow(ctx, out2[0], out2[1], p2(0.85, 0.5), { color: C.amber, width: 3.4, seed: 13, dash: [12, 9] });
    text(ctx, "SSH 反向隧道", 560, 468, { size: 28, p: tp, color: C.amber });
    text(ctx, "从你的电脑出境", 700, 808, { size: 28, p: op, color: C.amber });
    if (op >= 1) {
      const u = (s.L(2) * 0.35) % 1;
      dot(ctx, pointAt([...tunnel, ...out1], u), 9, C.amber);
    }
  },
};

const turn: Scene = {
  id: "turn",
  draw(ctx, s) {
    // 第一句：三道前置决策
    const pre = [["选技能", 0.12], ["选模型", 0.34], ["翻记忆", 0.56]] as const;
    pre.forEach(([name, f], i) => {
      const p = s.at(0, f, 0.9);
      node(ctx, 110 + i * 300, 200, 230, 90, name, ["JEV 两级", "本地 / 云端", "关键词 + JEV"][i], p, { align: "center", fill: "rgba(255,255,255,0.5)" });
      if (i < 2) arrow(ctx, [345 + i * 300, 245], [405 + i * 300, 245], s.at(0, f + 0.12, 0.6), { width: 2.6, seed: 20 + i });
    });
    text(ctx, "你说一句话", 110, 160, { size: 30, p: s.p(0, 0, 0.8), color: C.soft });
    arrow(ctx, [800, 290], [980, 400], s.at(0, 0.8, 0.8), { width: 2.6, seed: 24 }, -30);
    // 第二句：规划循环
    const cx = 1150, cy = 560, r = 210;
    const loop = [["模型提出调用", -Math.PI / 2], ["门控", 0], ["执行", Math.PI / 2], ["结果回填", Math.PI]] as const;
    const ring = s.p(1, 0.1, 1.6);
    stroke(ctx, Array.from({ length: 49 }, (_, i) => [cx + Math.cos((i / 48) * Math.PI * 2) * r, cy + Math.sin((i / 48) * Math.PI * 2) * r] as Pt), ring, { color: C.green, width: 3, seed: 30 });
    text(ctx, "规划循环", cx, cy - 6, { size: 40, align: "center", p: ring });
    text(ctx, "最多 30 步", cx, cy + 40, { size: 26, align: "center", p: ring, color: C.soft });
    loop.forEach(([name, a], i) => {
      const p = s.at(1, 0.12 + i * 0.18, 0.8);
      const x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r;
      const w = name.length * 30 + 40;
      box(ctx, x - w / 2, y - 34, w, 68, p, { width: 2.6, seed: 40 + i, color: i === 1 ? C.amber : C.ink }, "rgba(247,241,229,0.95)", 30);
      text(ctx, name, x, y + 11, { size: 30, align: "center", p, color: i === 1 ? C.amber : C.ink });
    });
    if (s.L(1) > 1.2) {
      const a = -Math.PI / 2 + (s.L(1) - 1.2) * 1.8;
      dot(ctx, [cx + Math.cos(a) * r, cy + Math.sin(a) * r], 12, C.amber);
    }
    // 第三句：回复与写回
    const rp = s.at(2, 0.05, 0.8), wp = s.at(2, 0.3, 0.8);
    arrow(ctx, [cx + r + 20, cy - 80], [1500, 330], rp, { width: 2.6, seed: 50 }, -20);
    node(ctx, 1500, 270, 300, 90, "回复你", "", rp, { align: "center", fill: "rgba(122,190,132,0.18)" });
    arrow(ctx, [cx + r + 10, cy + 80], [1500, 700], wp, { width: 2.6, seed: 51 }, 20);
    node(ctx, 1500, 660, 300, 90, "写回记忆", "", wp, { align: "center" });
    // 轨迹纸条：每个决定一行
    const events = ["skill.select", "route.model", "memory.recall", "llm.call", "tool.gate", "tool.call", "turn.end"];
    const times = [s.at(0, 0.2), s.at(0, 0.42), s.at(0, 0.64), s.at(1, 0.2), s.at(1, 0.38), s.at(1, 0.55), s.at(2, 0.1)];
    const tp = s.p(0, 0.2, 0.8);
    box(ctx, 110, 400, 560, 420, tp, { color: C.soft, width: 2.2, seed: 60 }, "rgba(255,255,255,0.55)", 8);
    text(ctx, "trace.jsonl", 134, 446, { size: 26, p: tp, font: "mono", color: C.soft });
    events.forEach((ev, i) => text(ctx, `{"type": "${ev}", …}`, 134, 500 + i * 44, { size: 24, p: times[i], font: "mono", color: i === 4 ? C.amber : C.ink }));
    highlight(ctx, 128, 800, 500, 16, s.at(2, 0.6, 0.8), C.hlGreen);
    text(ctx, "每个决定一行", 134, 806, { size: 28, p: s.at(2, 0.6, 0.8) });
  },
};

export const part1: Scene[] = [intro, flow, arch, turn];
void lerp;
