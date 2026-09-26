import {
  ArrowUpRight, Brain, Check, CircleSlash, Cloud, Cpu, FileText, Gauge, Layers, ListChecks, Route, ShieldCheck,
  CornerDownLeft, Sparkles, TriangleAlert, Users, Wrench, X,
} from "lucide";
import {
  DIFFICULTY_LABEL, ENDPOINT_LABEL, GATE_LABEL, ms, num, PERMISSION_LABEL, skillName, TIER_LABEL, tokens,
} from "../format";
import { state, update } from "../store";
import type { TraceEvent, Turn } from "../types";
import { h, icon, type Child } from "./dom";

/** 概率条：value 0..1，threshold 画一条竖线，达标的条用强调色 */
function bar(label: string, value: number, opts: { threshold?: number; strong?: boolean; invert?: boolean } = {}) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const pass = opts.threshold === undefined ? opts.strong : opts.invert ? value < opts.threshold : value >= opts.threshold;
  return h("div", { class: "bar-row" },
    h("span", { class: "bar-label", title: label }, label),
    h("span", { class: "bar-track" },
      h("span", { class: ["bar-fill", pass && "pass", opts.invert && !pass && "danger"], style: `width:${pct}%` }),
      opts.threshold !== undefined &&
        h("span", { class: "bar-tick", style: `left:${opts.threshold * 100}%`, title: `阈值 ${opts.threshold}` })),
    h("span", { class: "bar-value mono" }, num(value)));
}

function card(iconNode: any, title: string, badge: HTMLElement | null, ...body: Child[]) {
  return h("section", { class: "tcard" },
    h("header", { class: "tcard-head" }, icon(iconNode, 15), h("span", null, title), badge),
    ...body);
}

function badge(text: string, kind = ""): HTMLElement {
  return h("span", { class: `badge ${kind}` }, text);
}

function find(t: Turn, type: string): TraceEvent | undefined {
  return t.events.find((e) => e.type === type);
}

function skillCard(t: Turn): HTMLElement | null {
  const ev = find(t, "skill.select");
  if (!ev) return null;
  const d = ev.data;
  const mode = d.mode === "jev" ? badge("JEV 两级", "accent") : badge(ev.fallback ? "降级 · 主模型自选" : "主模型自选", ev.fallback ? "warn" : "");
  const selected: string[] = d.selected ?? [];
  const probs = Object.entries((d.stage1?.probabilities ?? {}) as Record<string, number>).slice(0, 5);
  const fits = Object.entries((d.stage2 ?? {}) as Record<string, number>);
  return card(Sparkles, "技能选择", mode,
    h("div", { class: "result-row" },
      selected.length ? selected.map((s) => h("span", { class: "chip skill" }, s)) : h("span", { class: "chip" }, icon(CircleSlash, 12), "不用技能"),
      d.cached ? h("span", { class: "muted small", title: "同样的问题问过 JEV，直接用了缓存结果" }, "命中缓存")
        : ev.latency_ms !== undefined && h("span", { class: "muted mono" }, ms(ev.latency_ms))),
    d.gate && h("div", { class: "tblock" },
      h("div", { class: "tblock-title" }, "要不要用技能", h("span", { class: "hint" }, "三问平均，竖线是阈值")),
      bar("门控值", d.gate.value, { threshold: d.gate.threshold }),
      h("div", { class: "sub-bars" },
        bar("要动仓库/任务", d.gate.acts),
        bar("有既定流程", d.gate.procedure),
        bar("光说就够（反向）", d.gate.prose))),
    probs.length > 0 && h("div", { class: "tblock" },
      h("div", { class: "tblock-title" }, "第一级 · 候选概率"),
      probs.map(([k, v]) => bar(skillName(k), v, { strong: k === d.stage1?.top }))),
    fits.length > 0 && h("div", { class: "tblock" },
      h("div", { class: "tblock-title" }, "第二级 · 是否合适", h("span", { class: "hint" }, "≥0.30 可选，≥0.50 可组合")),
      fits.map(([k, v]) => bar(skillName(k), v, { threshold: 0.3 }))),
    d.reason && h("p", { class: "reason" }, d.reason));
}

function routeCard(t: Turn): HTMLElement | null {
  const ev = find(t, "route.model");
  if (!ev) return null;
  const d = ev.data;
  const escalations = t.events.filter((e) => e.type === "route.escalate");
  const diff = (d.scores?.difficulty ?? {}) as Record<string, number>;
  return card(Route, "模型路由", badge(TIER_LABEL[d.tier] ?? d.tier, d.tier === "cloud" ? "cloud" : "local"),
    h("div", { class: "result-row" }, icon(d.tier === "cloud" ? Cloud : Cpu, 14), h("span", { class: "mono" }, d.model),
      ev.fallback && badge("降级", "warn")),
    Object.keys(diff).length > 0 && h("div", { class: "tblock" },
      h("div", { class: "tblock-title" }, "难度判断", h("span", { class: "hint" }, "困难 ≥0.50 交给难题模型")),
      ["simple", "moderate", "hard"].filter((k) => k in diff).map((k) =>
        bar(DIFFICULTY_LABEL[k], diff[k], k === "hard" ? { threshold: 0.5 } : {})),
      d.scores?.writes_code !== undefined && bar("要写代码", d.scores.writes_code, { threshold: 0.8 })),
    h("p", { class: "reason" }, d.reason),
    escalations.map((e) => h("div", { class: "escalate" }, icon(ArrowUpRight, 13),
      `${ENDPOINT_LABEL[e.data.from] ?? e.data.from} → ${ENDPOINT_LABEL[e.data.to] ?? e.data.to}：${e.data.reason}`)));
}

function memoryCard(t: Turn): HTMLElement | null {
  const ev = find(t, "memory.recall");
  const write = find(t, "memory.write");
  if (!ev && !write) return null;
  const d = ev?.data ?? {};
  const rel = (d.relevance ?? {}) as Record<string, number>;
  const item = (id: string, place: string) => {
    const m = state.memories.get(id);
    return h("div", { class: "mem" },
      h("span", { class: `tag ${place === "原文" ? "accent" : ""}` }, place),
      h("span", { class: "mem-text", title: m?.content ?? "" }, m ? m.content : `记忆 ${id}`),
      rel[id] !== undefined && h("span", { class: "mono muted" }, num(rel[id])));
  };
  const writes = ((write?.data.items ?? []) as any[]).filter((i) => i.layer && i.layer !== "episodic");
  return card(Brain, "长期记忆", ev?.fallback ? badge("降级 · 关键词", "warn") : null,
    ev && h("div", { class: "muted small" },
      `关键词召回 ${d.candidates?.length ?? 0} 条 → 原文 ${d.full?.length ?? 0} · 摘要 ${d.brief?.length ?? 0}`,
      d.excluded_private?.length ? ` · ${d.excluded_private.length} 条隐私记忆没带给外部模型` : ""),
    ev && (d.full ?? []).map((id: string) => item(id, "原文")),
    ev && (d.brief ?? []).map((id: string) => item(id, "摘要")),
    writes.length > 0 && h("div", { class: "tblock" },
      h("div", { class: "tblock-title" }, "这一轮记下的"),
      writes.map((i) => h("div", { class: "mem" },
        h("span", { class: `tag ${i.status === "active" ? "accent" : ""}` }, i.status === "active" ? "已生效" : "待确认"),
        h("span", { class: "mem-text" }, state.memories.get(i.id)?.content ?? i.kind),
        i.worth !== undefined && i.worth !== null && h("span", { class: "mono muted" }, num(i.worth))))));
}

function stepItem(e: TraceEvent): HTMLElement | null {
  const d = e.data;
  switch (e.type) {
    case "llm.call": {
      const u = e.usage;
      return h("li", { class: "step llm" },
        h("span", { class: "step-dot" }),
        h("div", { class: "step-body" },
          h("div", { class: "step-title" }, `第 ${d.step} 步 · ${ENDPOINT_LABEL[d.endpoint] ?? d.endpoint}`,
            e.model && h("span", { class: "mono muted" }, e.model),
            h("span", { class: "mono muted" }, ms(e.latency_ms))),
          h("div", { class: "step-sub" },
            (d.tool_calls ?? []).length ? (d.tool_calls as string[]).map((n) => h("code", null, n)) : h("span", null, "给出回复"),
            u && h("span", { class: "mono muted" }, `↑${tokens(u.input_tokens)} ↓${tokens(u.output_tokens)}`))));
    }
    case "tool.gate": {
      if (d.permission === "read") return null;
      const kind = d.decision === "allow" ? "pass" : d.decision === "deny" ? "danger" : "warn";
      return h("li", { class: `step gate ${kind}` },
        icon(ShieldCheck, 13, "step-icon"),
        h("div", { class: "step-body" },
          h("div", { class: "step-title" }, h("code", null, d.tool), badge(GATE_LABEL[d.decision] ?? d.decision, kind),
            h("span", { class: "muted small" }, PERMISSION_LABEL[d.permission] ?? d.permission),
            d.decision === "confirm" && d.confirmed !== null &&
              h("span", { class: "muted small" }, d.confirmed ? "· 你同意了" : "· 你拒绝了")),
          (d.appropriate !== null || d.collateral !== null) && h("div", { class: "step-sub mono muted" },
            `合理 ${num(d.appropriate)} · 越界 ${num(d.collateral)}`)));
    }
    case "tool.call":
      return h("li", { class: ["step tool", !d.ok && "fail"] },
        icon(d.ok ? Check : X, 13, "step-icon"),
        h("div", { class: "step-body" }, h("div", { class: "step-title" }, h("code", null, d.tool),
          d.truncated && h("span", { class: "muted small" }, "结果已截断"),
          d.error && h("span", { class: "muted small" }, d.error),
          h("span", { class: "mono muted" }, ms(e.latency_ms)))));
    case "route.escalate":
      return h("li", { class: "step warn" }, icon(ArrowUpRight, 13, "step-icon"),
        h("div", { class: "step-body" }, h("div", { class: "step-title" },
          `切换 ${ENDPOINT_LABEL[d.from] ?? d.from} → ${ENDPOINT_LABEL[d.to] ?? d.to}`), h("div", { class: "step-sub" }, d.reason)));
    case "context.compress":
      return h("li", { class: "step" }, icon(Layers, 13, "step-icon"),
        h("div", { class: "step-body" }, h("div", { class: "step-title" },
          d.noop ? "超预算，但近几轮受保护，这次不压" : `压缩上下文 ${tokens(d.before_tokens)} → ${tokens(d.after_tokens)}`),
          (d.chunks ?? []).length > 0 && h("div", { class: "step-sub" },
            (d.chunks as any[]).map((c) => h("span", { class: "tag" },
              `${c.id} ${c.verdict === "drop" ? "丢弃" : c.verdict === "summarize_forced" ? "强制摘要" : "留摘要"}`)))));
    case "subagent.start":
      return h("li", { class: "step sub" }, icon(Users, 13, "step-icon"),
        h("div", { class: "step-body" },
          h("div", { class: "step-title" }, "派出子助手", h("span", null, d.description),
            h("span", { class: "mono muted" }, d.model)),
          h("div", { class: "step-sub muted" }, d.prompt)));
    case "subagent.end":
      return h("li", { class: ["step sub", !d.ok && "warn"] }, icon(d.ok ? CornerDownLeft : TriangleAlert, 13, "step-icon"),
        h("div", { class: "step-body" },
          h("div", { class: "step-title" }, d.ok ? "子助手交回" : "子助手未完成", h("span", null, d.description),
            h("span", { class: "mono muted" }, `${d.steps} 步 · ${ms(e.latency_ms)}`)),
          (d.tools ?? []).length > 0 && h("div", { class: "step-sub" },
            [...new Set(d.tools as string[])].map((n) => h("code", null, n))),
          h("details", { class: "sub-answer" }, h("summary", null, "看结论"), h("p", null, d.answer))));
    case "error":
      return h("li", { class: "step danger" }, icon(TriangleAlert, 13, "step-icon"),
        h("div", { class: "step-body" }, h("div", { class: "step-title" }, d.handled ? "已自动处理" : "出错"),
          h("div", { class: "step-sub" }, d.message)));
    default:
      return null;
  }
}

function stepsCard(t: Turn): HTMLElement | null {
  const items = t.events.map(stepItem).filter(Boolean) as HTMLElement[];
  if (!items.length) return null;
  return card(ListChecks, "执行过程", badge(`${t.events.filter((e) => e.type === "llm.call").length} 步`),
    h("ol", { class: "steps" }, items));
}

function usageCard(t: Turn): HTMLElement | null {
  const end = find(t, "turn.end");
  const toks = (end?.data.tokens ?? t.done?.tokens ?? {}) as Record<string, { input_tokens: number; output_tokens: number }>;
  const rows = Object.entries(toks);
  if (!rows.length && !end) return null;
  return card(Gauge, "用量", end ? badge(ms(end.latency_ms)) : null,
    h("table", { class: "usage" },
      h("tr", null, h("th", null, "服务"), h("th", null, "输入"), h("th", null, "输出")),
      rows.map(([k, u]) => h("tr", null, h("td", null, ENDPOINT_LABEL[k] ?? k),
        h("td", { class: "mono" }, tokens(u.input_tokens)), h("td", { class: "mono" }, tokens(u.output_tokens))))),
    end?.data.stopped && end.data.stopped !== "final" &&
      h("p", { class: "reason warn-text" }, end.data.stopped === "max_steps" ? "这一轮走到了步数上限" : "这一轮出错结束"));
}

function workingView(): HTMLElement {
  const w = state.current?.working;
  if (!w || (!w.goal && !w.todo.length && !w.evidence.length))
    return h("div", { class: "trace-empty" }, icon(FileText, 20), h("p", null, "多步任务开始后，agent 会在这里记下目标、待办和关键证据。它们不会被上下文压缩丢掉。"));
  return h("div", { class: "working" },
    h("section", { class: "tcard" }, h("header", { class: "tcard-head" }, icon(ListChecks, 15), "目标"), h("p", { class: "goal" }, w.goal || "（未设定）")),
    w.constraints.length > 0 && h("section", { class: "tcard" }, h("header", { class: "tcard-head" }, "约束"),
      h("ul", { class: "plain" }, w.constraints.map((c) => h("li", null, c)))),
    w.todo.length > 0 && h("section", { class: "tcard" }, h("header", { class: "tcard-head" }, "待办",
      badge(`${w.todo.filter((x) => x.done).length}/${w.todo.length}`)),
      h("ul", { class: "todo" }, w.todo.map((x) => h("li", { class: x.done ? "done" : "" },
        h("span", { class: "check" }, x.done && icon(Check, 12)), x.item)))),
    w.evidence.length > 0 && h("section", { class: "tcard" }, h("header", { class: "tcard-head" }, icon(Wrench, 15), "关键证据"),
      h("ul", { class: "plain evidence" }, w.evidence.map((e) => h("li", null, e)))));
}

export function renderTracePanel(): HTMLElement {
  const cur = state.current;
  const t = cur && state.selectedTurn !== null ? cur.turns.get(state.selectedTurn) : undefined;
  const tabs = h("div", { class: "tabs" },
    h("button", { class: ["tab", state.rightTab === "trace" && "on"], onclick: () => update((s) => (s.rightTab = "trace")) }, "决策轨迹"),
    h("button", { class: ["tab", state.rightTab === "working" && "on"], onclick: () => update((s) => (s.rightTab = "working")) },
      "工作记忆", cur?.working?.todo.length ? h("span", { class: "count" }, String(cur.working.todo.filter((x) => !x.done).length || "")) : null));
  let body: HTMLElement;
  if (state.rightTab === "working") body = workingView();
  else if (!t) body = h("div", { class: "trace-empty" }, icon(Sparkles, 20),
    h("p", null, "每一轮里 agent 做的结构化决策——选哪个技能、用哪个模型、哪次写操作要确认——都会按顺序出现在这里。"));
  else {
    const running = cur!.busy && !t.done;
    body = h("div", { class: "trace-body" },
      h("div", { class: "trace-title" }, `第 ${t.n} 轮`, running ? badge("进行中", "run") : t.done?.latency ? h("span", { class: "muted mono" }, ms(t.done.latency * 1000)) : null),
      t.input && h("p", { class: "trace-input" }, t.input),
      skillCard(t), routeCard(t), memoryCard(t), stepsCard(t), usageCard(t));
  }
  return h("div", { class: "panel-inner" }, tabs, h("div", { class: "panel-scroll" }, body));
}
