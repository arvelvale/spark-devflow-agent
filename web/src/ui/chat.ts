import {
  Bot, Check, ChevronRight, Cloud, Cpu, LoaderCircle, Mic, ShieldAlert, Sparkles, TriangleAlert, X,
} from "lucide";
import { ms, num, PERMISSION_LABEL, TIER_LABEL } from "../format";
import { answerConfirm, sendTurn, selectTurn, sortedTurns, state, type Current } from "../store";
import type { ConfirmItem, Turn } from "../types";
import { h, icon } from "./dom";
import { markdown } from "./markdown";

const SUGGESTIONS = [
  "待会开站会，帮我理一下昨天干了啥今天干啥",
  "把 DAY-298 金额累加精度的 bug 修掉，记得补测试",
  "把昨天周会纪要里的待办建成 Linear 任务",
  "帮我 review 一下当前分支，看有没有违反 AGENTS.md",
];

/** 一轮当前在干什么（给进行中的轮次一句人话） */
function progressText(t: Turn): string {
  const last = t.events[t.events.length - 1];
  if (!last) return "收到，正在准备";
  const steps = t.events.filter((e) => e.type === "llm.call").length;
  switch (last.type) {
    case "turn.start": return "正在挑选合适的技能";
    case "skill.select": return "正在决定交给主力还是难题模型";
    case "route.model": return "正在翻相关的长期记忆";
    case "memory.recall": return "模型开始思考了";
    case "llm.call": {
      const calls: string[] = last.data.tool_calls ?? [];
      return calls.length ? `第 ${steps} 步 · 正在执行 ${calls.join("、")}` : `第 ${steps} 步 · 正在整理回复`;
    }
    case "tool.gate": return last.data.decision === "confirm" ? "等你确认一个写操作" : `正在执行 ${last.data.tool}`;
    case "tool.call": return `第 ${steps} 步完成，模型继续思考`;
    case "context.compress": return "上下文有点长，正在压缩";
    case "route.escalate": return `换到 ${last.data.to} 模型继续`;
    case "memory.write": return "正在记下值得记住的事";
    case "subagent.start": return "子助手正在并行调查";
    case "subagent.end": return "子助手交回了结论";
    default: return "进行中";
  }
}

function decisionStrip(t: Turn): HTMLElement | null {
  const sel = t.events.find((e) => e.type === "skill.select");
  const routes = t.events.filter((e) => e.type === "route.model" || e.type === "route.escalate");
  if (!sel && !routes.length) return null;
  const route = routes[routes.length - 1];
  const tier = route?.type === "route.escalate" ? (route.data.to === "cloud" ? "cloud" : "local") : route?.data.tier;
  const steps = t.events.filter((e) => e.type === "llm.call").length;
  const skills: string[] = sel?.data.selected ?? [];
  const gates = t.events.filter((e) => e.type === "tool.gate" && e.data.permission !== "read");
  const active = state.selectedTurn === t.n;
  return h("button", { class: ["strip", active && "active"], title: "在右侧查看这一轮的决策轨迹", onclick: () => selectTurn(t.n) },
    h("span", { class: "chip skill" }, icon(Sparkles, 13), skills.length ? skills.join(" + ") : "不用技能"),
    tier && h("span", { class: `chip tier ${tier}` }, icon(tier === "cloud" ? Cloud : Cpu, 13), TIER_LABEL[tier] ?? tier),
    steps > 0 && h("span", { class: "chip" }, `${steps} 步`),
    gates.length > 0 && h("span", { class: "chip" }, `${gates.length} 次写操作门控`),
    t.done?.latency !== undefined && h("span", { class: "chip" }, ms(t.done.latency * 1000)),
    sel?.fallback && h("span", { class: "chip warn" }, icon(TriangleAlert, 12), "降级"),
    h("span", { class: "strip-more" }, "轨迹", icon(ChevronRight, 13)));
}

function argPreview(c: ConfirmItem): HTMLElement {
  const a = c.arguments as Record<string, any>;
  const lines = (text: unknown, mark: string, cls: string, max = 14) => {
    const all = String(text ?? "").split("\n");
    const shown = all.slice(0, max).map((l) => h("div", { class: `diff-line ${cls}` }, `${mark} ${l}`));
    if (all.length > max) shown.push(h("div", { class: "diff-line more" }, `…还有 ${all.length - max} 行`));
    return shown;
  };
  if (c.tool === "edit_file")
    return h("div", { class: "args" }, h("div", { class: "args-path" }, a.path), h("div", { class: "diff" },
      lines(a.old, "−", "del"), lines(a.new, "+", "add")));
  if (c.tool === "write_file")
    return h("div", { class: "args" }, h("div", { class: "args-path" }, `${a.path}（整份写入）`),
      h("div", { class: "diff" }, lines(a.content, "+", "add")));
  if (c.tool === "run_command") return h("div", { class: "args" }, h("code", { class: "cmd" }, a.command));
  if (c.tool === "git_commit") return h("div", { class: "args" }, h("div", { class: "args-kv" }, "提交说明：", a.message));
  if (c.tool === "linear_create_issue")
    return h("div", { class: "args" }, h("div", { class: "args-kv strong" }, a.title),
      a.parent && h("div", { class: "args-kv" }, `父任务 ${a.parent}`),
      a.description && h("div", { class: "diff" }, lines(a.description, " ", "ctx", 10)));
  if (c.tool === "linear_update_issue")
    return h("div", { class: "args" }, h("div", { class: "args-kv strong" }, a.identifier),
      a.state && h("div", { class: "args-kv" }, `状态改为：${a.state}`),
      a.comment && h("div", { class: "diff" }, lines(a.comment, " ", "ctx", 8)));
  return h("div", { class: "args" }, h("pre", { class: "json" }, JSON.stringify(a, null, 2).slice(0, 1500)));
}

function scoreRow(label: string, v: number | null, danger: boolean): HTMLElement {
  const pct = v === null ? 0 : Math.round(v * 100);
  return h("div", { class: "mini-score" },
    h("span", null, label),
    h("span", { class: "mini-track" }, h("span", { class: ["mini-fill", danger && "danger"], style: `width:${pct}%` })),
    h("span", { class: "mono" }, num(v)));
}

function confirmCard(c: ConfirmItem): HTMLElement {
  if (c.resolved) {
    const label = c.resolved.timeout ? "等太久没回应，已按拒绝处理" : c.resolved.approve ? "你同意了" : "你拒绝了";
    return h("div", { class: ["confirm-done", c.resolved.approve ? "yes" : "no"] },
      icon(c.resolved.approve ? Check : X, 14), `${label} · ${c.tool}`);
  }
  const external = c.permission === "external";
  return h("div", { class: ["confirm", external && "external"] },
    h("div", { class: "confirm-head" }, icon(ShieldAlert, 16),
      h("span", null, external ? "这个操作别人也能看到，确认一下" : "要改动文件，确认一下"),
      h("span", { class: "tag" }, PERMISSION_LABEL[c.permission] ?? c.permission)),
    h("div", { class: "confirm-tool" }, h("code", null, c.tool), h("span", { class: "confirm-reason" }, c.reason)),
    (c.in_scope !== null || c.collateral !== null) && h("div", { class: "confirm-scores" },
      scoreRow("合理步骤", c.in_scope, false), scoreRow("越界风险", c.collateral, true)),
    argPreview(c),
    h("div", { class: "confirm-actions" },
      h("button", { class: "btn ghost", onclick: () => void answerConfirm(c.id, false) }, "不行"),
      h("button", { class: "btn primary", onclick: () => void answerConfirm(c.id, true) }, "同意执行")));
}

function turnView(cur: Current, t: Turn, running: boolean): HTMLElement {
  const confirms = [...cur.confirms.values()].filter((c) => c.turn === t.n);
  return h("section", { class: "turn", dataset: { turn: String(t.n) } },
    t.input && h("div", { class: "msg user" }, h("div", { class: "bubble" },
      t.source === "voice" && h("span", { class: "voice-tag", title: "语音输入" }, icon(Mic, 12)), t.input)),
    decisionStrip(t),
    confirms.map(confirmCard),
    t.reply
      ? h("div", { class: "msg bot" }, h("div", { class: "avatar" }, icon(Bot, 16)), markdown(t.reply))
      : running && h("div", { class: "progress" }, icon(LoaderCircle, 14, "spin"), progressText(t)));
}

function emptyState(cur: Current | null): HTMLElement {
  const skills = state.status?.skills ?? [];
  return h("div", { class: "empty" },
    h("div", { class: "empty-mark" }, icon(Sparkles, 20)),
    h("h2", null, cur ? "今天想推进点什么？" : "从左边新建一个对话开始"),
    h("p", null, "我会先挑技能、选模型，再动手；写文件和改 Linear 之前都会先问你。每一步决策都记在右边。"),
    cur?.live && h("div", { class: "suggest" },
      SUGGESTIONS.map((text) => h("button", { class: "suggest-item", onclick: () => void sendTurn(text, "text") }, text))),
    skills.length > 0 && h("div", { class: "skill-cloud" },
      h("div", { class: "skill-cloud-label" }, `已装 ${skills.length} 个技能`),
      skills.map((s) => h("span", { class: "skill-pill", title: s.description }, s.name))));
}

export function renderMessages(): HTMLElement {
  const cur = state.current;
  const turns = sortedTurns(cur);
  if (!cur || (!turns.length && !cur.pendingInput)) return emptyState(cur);
  const lastN = turns.length ? turns[turns.length - 1].n : 0;
  return h("div", { class: "messages-inner" },
    turns.map((t) => turnView(cur, t, cur.busy && t.n === lastN && !t.done)),
    cur.pendingInput && h("section", { class: "turn" },
      h("div", { class: "msg user" }, h("div", { class: "bubble" }, cur.pendingInput.text)),
      h("div", { class: "progress" }, icon(LoaderCircle, 14, "spin"), "收到，正在准备")),
    cur.stream === "reconnecting" && h("div", { class: "banner" }, "和面板后端的连接断了，正在重连…"));
}
