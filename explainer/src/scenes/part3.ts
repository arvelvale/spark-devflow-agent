// 第 9–11 章：真机实测、接下来五天、结尾
import { bar, box, C, check, circle, clamp01, highlight, stamp, stroke, text } from "../engine/ink";
import { chip, type Scene } from "./common";

const evidence: Scene = {
  id: "evidence",
  draw(ctx, s) {
    // 第一句：一张"工作记录"纸条，跟着念的顺序一行行打勾
    const pp = s.p(0, 0, 0.8);
    box(ctx, 110, 180, 800, 640, pp, { width: 2.6, seed: 3 }, "rgba(255,255,255,0.6)", 10);
    text(ctx, "DAY-298 · 节点真机", 140, 236, { size: 30, p: pp, color: C.soft });
    const rows = [["读 issue 和代码", 0.08], ["新建分支 agent/day-298-cents", 0.2], ["金额 → 按分存整数", 0.38], ["测试从 3 个补到 7 个", 0.58], ["全部通过", 0.8]] as const;
    rows.forEach(([t, f], i) => {
      const p = s.at(0, f, 0.8);
      text(ctx, t, 200, 320 + i * 86, { size: 34, p, font: i === 1 ? "mono" : "hand" });
      check(ctx, 160, 308 + i * 86, 30, s.at(0, f + 0.06, 0.5));
    });
    text(ctx, "25 步 · 284 秒", 200, 790, { size: 30, p: s.at(0, 0.9), color: C.soft });
    // 第二句：A/B
    const ab = s.p(1, 0, 1);
    text(ctx, "技能选择 A/B · 26 条", 1040, 236, { size: 32, p: ab });
    const groups = [["硬凑技能", [0, 0.143], ["0%", "14.3%"]], ["完全正确", [1, 0.885], ["100%", "88.5%"]]] as const;
    groups.forEach(([name, vals, labels], g) => {
      const y = 300 + g * 250;
      const p = s.at(1, 0.15 + g * 0.35, 1);
      text(ctx, name, 1040, y + 30, { size: 30, p });
      ["JEV", "主模型自选"].forEach((arm, k) => {
        text(ctx, arm, 1060, y + 90 + k * 64, { size: 24, p, color: C.soft });
        bar(ctx, 1230, y + 64 + k * 64, 440, 40, vals[k], p, k ? C.faint : C.green, 40 + g * 2 + k);
        text(ctx, labels[k], 1690, y + 92 + k * 64, { size: 26, p, font: "mono" });
      });
    });
    // 第三句：满分打星号
    const fn = s.at(2, 0.1, 0.8);
    circle(ctx, 1715, 614, 56, fn, { color: C.red, width: 3, seed: 60 });
    text(ctx, "*", 1774, 580, { size: 70, p: fn, color: C.red });
    text(ctx, "* 在调阈值的同一批题上测的", 1040, 880, { size: 32, p: s.at(2, 0.3, 1), color: C.red });
    stroke(ctx, Array.from({ length: 30 }, (_, i) => [1040 + i * 22, 902 + Math.sin(i * 1.3) * 5]), s.at(2, 0.5, 1), { color: C.red, width: 2.6, seed: 61 });
    text(ctx, "还需要一组没见过的题", 1040, 950, { size: 32, p: s.at(2, 0.65, 1) });
  },
};

const plan: Scene = {
  id: "plan",
  draw(ctx, s) {
    const people = [
      ["晨熠", "架构 · 对外", ["对外 README", "演示视频"], C.green],
      ["agent 优化", "路由 · 压缩 · 记忆", ["留出集验证", "路由标定"], C.blue],
      ["提示词优化", "提示词 · JEV 题目", ["门控标定集 → 30+", "分模型适配提示词"], C.amber],
      ["skills 优化", "技能 · 任务集", ["任务集 → 60+", "补内部技能"], C.red],
    ] as const;
    people.forEach(([name, role, tasks, col], i) => {
      const x = 110 + i * 440, p = s.at(0, 0.1 + i * 0.12, 0.8);
      const rot = [-0.02, 0.015, -0.01, 0.02][i];
      ctx.save();
      ctx.translate(x + 190, 430);
      ctx.rotate(rot);
      ctx.translate(-(x + 190), -430);
      box(ctx, x, 200, 380, 460, p, { width: 2.6, seed: 10 + i, color: col }, "rgba(255,255,255,0.62)", 8);
      stroke(ctx, [[x, 280], [x + 380, 280]], p, { color: col, width: 2, seed: 20 + i, double: false });
      text(ctx, name, x + 24, 256, { size: 38, p });
      text(ctx, role, x + 24, 326, { size: 24, p, color: C.soft });
      tasks.forEach((t, k) => {
        const tp = s.at(1, 0.06 + i * 0.22 + k * 0.08, 0.9);
        text(ctx, `· ${t}`, x + 24, 400 + k * 70, { size: 30, p: tp });
      });
      ctx.restore();
    });
    // 第三句：日历条，圈住 29 号
    const cp = s.p(2, 0, 1);
    ["24", "25", "26", "27", "28", "29"].forEach((d, i) => {
      const x = 330 + i * 210;
      box(ctx, x, 760, 170, 110, clamp01(cp * 1.5 - i * 0.08), { width: 2.2, seed: 40 + i, color: C.soft }, i === 5 ? "rgba(232,120,100,0.12)" : "rgba(255,255,255,0.5)", 8);
      text(ctx, `9/${d}`, x + 85, 830, { size: 34, align: "center", p: clamp01(cp * 1.5 - i * 0.08), font: "mono" });
    });
    circle(ctx, 1465, 815, 110, s.p(2, 0.9, 0.9), { color: C.red, width: 4, seed: 60 });
    text(ctx, "23:59 截止", 1600, 940, { size: 36, p: s.p(2, 1.4, 0.8), color: C.red });
  },
};

const outro: Scene = {
  id: "outro",
  draw(ctx, s) {
    const items = ["选技能", "选模型", "放不放行", "丢不丢上下文"];
    const a = 1 - s.p(1, 0, 0.6) * 0.75;
    ctx.save();
    ctx.globalAlpha *= a;
    items.forEach((t, i) => {
      const p = s.at(0, 0.02 + i * 0.13, 0.7);
      text(ctx, t, 640, 260 + i * 110, { size: 52, p });
      check(ctx, 1100, 244 + i * 110, 50, s.at(0, 0.08 + i * 0.13, 0.5));
    });
    const rp = s.at(0, 0.62, 1.2);
    box(ctx, 560, 720, 800, 70, rp, { width: 3, seed: 30 }, "rgba(248,208,72,0.35)", 6);
    for (let i = 1; i < 40; i++) stroke(ctx, [[560 + i * 20, 720], [560 + i * 20, 720 + (i % 5 ? 16 : 30)]], clamp01(rp * 1.4 - i / 60), { width: 2, seed: 40 + i, double: false });
    text(ctx, "每一个「选哪个」，都可以被度量", 960, 870, { size: 44, align: "center", p: s.at(0, 0.78, 1.2) });
    ctx.restore();
    const tp = s.p(1, 0.1, 1.2);
    if (tp > 0) {
      ctx.fillStyle = `rgba(243, 236, 221, ${0.82 * clamp01(tp * 2)})`;
      ctx.fillRect(0, 0, 1920, 1080);
      highlight(ctx, 690, 450, 540, 64, s.p(1, 0.8, 0.8), C.hlGreen);
      text(ctx, "Spark 开发流", 960, 500, { size: 110, align: "center", p: tp, weight: 700 });
      chip(ctx, 690, 600, "github.com/arvelvale/spark-devflow-agent", s.p(1, 1, 1), C.soft, "rgba(255,255,255,0.5)", 28);
      stamp(ctx, "DGX Spark", 1560, 330, s.p(1, 1.6, 0.6), C.green, 0.12, 34);
    }
  },
};

export const part3: Scene[] = [evidence, plan, outro];
