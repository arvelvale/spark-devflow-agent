import { Brain, CircleDot, FolderGit2, LogOut, Plus, Radio, SlidersHorizontal, X } from "lucide";
import { when } from "../format";
import { createSession, logout, openSession, setMemoryTab, state, update } from "../store";
import { h, icon } from "./dom";

const SERVICE_ROWS: { key: "local" | "backup" | "cloud" | "jev" | "linear"; label: string }[] = [
  { key: "local", label: "主力" },
  { key: "backup", label: "备用" },
  { key: "cloud", label: "难题" },
  { key: "jev", label: "JEV 决策" },
  { key: "linear", label: "Linear" },
];

function newSessionPanel(): HTMLElement {
  const ns = state.newSession;
  const seg = (value: string, label: string) =>
    h("button", {
      class: ["seg-btn", ns.tier === value && "on"],
      onclick: () => update((s) => (s.newSession.tier = value)),
    }, label);
  return h("div", { class: "popover" },
    h("div", { class: "popover-row" },
      h("div", null,
        h("div", { class: "popover-label" }, "JEV 决策层"),
        h("div", { class: "popover-hint" }, ns.useJev ? "技能、路由、门控都由 JEV 判断" : "基线：主模型自己选（A/B 对照用）")),
      h("button", {
        class: ["switch", ns.useJev && "on"], attrs: { role: "switch", "aria-checked": String(ns.useJev) },
        onclick: () => update((s) => (s.newSession.useJev = !s.newSession.useJev)),
      }, h("span", { class: "knob" }))),
    h("div", { class: "popover-row col" },
      h("div", { class: "popover-label" }, "模型档位"),
      h("div", { class: "seg" }, seg("auto", "自动"), seg("local", "主力"), seg("cloud", "难题"))),
    h("div", { class: "popover-actions" },
      h("button", { class: "btn ghost", onclick: () => update((s) => (s.newSessionOpen = false)) }, "取消"),
      h("button", { class: "btn primary", onclick: () => void createSession() }, "开始对话")));
}

export function renderSidebar(): HTMLElement {
  const st = state.status;
  const sessions = state.sessions;
  return h("div", { class: "sidebar-inner" },
    h("div", { class: "brand" },
      h("div", { class: "brand-mark" }, icon(Radio, 16)),
      h("div", null, h("div", { class: "brand-name" }, "Spark 开发流"), h("div", { class: "brand-sub" }, "跑在 DGX Spark 上")),
      h("button", { class: "icon-btn only-mobile", title: "收起", onclick: () => update((s) => (s.sidebarOpen = false)) },
        icon(X, 16))),
    h("div", { class: "new-wrap" },
      h("button", { class: "btn primary block", onclick: () => update((s) => (s.newSessionOpen = !s.newSessionOpen)) },
        icon(Plus, 16), "新对话"),
      state.newSessionOpen && newSessionPanel()),
    h("div", { class: "side-label" }, "会话"),
    h("div", { class: "session-list" },
      sessions.length === 0
        ? h("div", { class: "side-empty" }, "还没有会话，新建一个试试")
        : sessions.map((x) =>
            h("button", {
              class: ["session-item", state.current?.id === x.id && "active"],
              onclick: () => void openSession(x.id),
            },
            h("div", { class: "session-title" }, x.live && h("span", { class: "dot run", title: "在线" }), x.title),
            h("div", { class: "session-meta" }, `${x.turns} 轮 · ${when(x.updated)}`)))),
    h("div", { class: "side-foot" },
      h("button", { class: "side-link", onclick: () => { update((s) => (s.drawer = "memory")); void setMemoryTab(state.memoryTab); } },
        icon(Brain, 16), "长期记忆",
        h("span", { class: "count" }, String([...state.memories.values()].filter((m) => m.status === "pending").length || ""))),
      h("button", { class: "side-link", onclick: () => update((s) => (s.drawer = "models")) },
        icon(SlidersHorizontal, 16), "模型设置"),
      h("div", { class: "services" },
        SERVICE_ROWS.map(({ key, label }) => {
          const svc = st?.services[key];
          const cls = !svc ? "off" : svc.ok ? (key === "backup" ? "idle" : "run") : "warn";
          const priv = svc?.private === undefined ? "" : svc.private ? " · 私有" : " · 外部";
          return h("div", { class: "service", title: `${svc?.model ?? ""}${priv}` },
            h("span", { class: `dot ${cls}` }), h("span", { class: "service-label" }, label),
            h("span", { class: "service-model" }, svc?.model ?? "…"));
        })),
      st && h("div", { class: "workspace", title: "agent 操作的仓库" },
        icon(st.workspace_ready ? FolderGit2 : CircleDot, 14), st.workspace,
        !st.workspace_ready && h("span", { class: "warn-text" }, "未生成")),
      h("button", { class: "side-link subtle", onclick: () => void logout() }, icon(LogOut, 14), "退出登录")));
}
