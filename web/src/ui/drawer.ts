import { Lock, X } from "lucide";
import { when } from "../format";
import { approveMemory, forgetMemory, setMemoryTab, state, update } from "../store";
import { h, icon } from "./dom";

const KIND_LABEL: Record<string, string> = {
  event: "经历", fact: "事实", convention: "约定", decision: "决定", preference: "偏好",
};

export function renderDrawer(): HTMLElement | null {
  if (state.drawer !== "memory") return null;
  const tab = state.memoryTab;
  const list = state.memoryList.filter((m) => tab === "pending" || m.layer !== "episodic");
  const close = () => update((s) => (s.drawer = null));
  return h("div", { class: "drawer-mask", onclick: (e: MouseEvent) => e.target === e.currentTarget && close() },
    h("aside", { class: "drawer", attrs: { role: "dialog", "aria-label": "长期记忆" } },
      h("header", { class: "drawer-head" },
        h("div", null, h("h3", null, "长期记忆"),
          h("p", { class: "muted small" }, "跨会话记住的事实、约定和偏好。拿不准的会先放在「待确认」，由你决定。")),
        h("button", { class: "icon-btn", title: "关闭", onclick: close }, icon(X, 16))),
      h("div", { class: "tabs" },
        h("button", { class: ["tab", tab === "active" && "on"], onclick: () => void setMemoryTab("active") }, "生效中"),
        h("button", { class: ["tab", tab === "pending" && "on"], onclick: () => void setMemoryTab("pending") }, "待确认")),
      h("div", { class: "drawer-body" },
        list.length === 0
          ? h("p", { class: "muted drawer-empty" }, tab === "pending" ? "没有等你确认的记忆" : "还没有记下什么")
          : list.map((m) => h("div", { class: "mem-card" },
              h("div", { class: "mem-meta" },
                h("span", { class: "tag" }, KIND_LABEL[m.kind] ?? m.kind),
                m.privacy === "local" && h("span", { class: "tag", title: "隐私记忆：不会发给 JEV 和云端模型" }, icon(Lock, 11), "仅本地"),
                h("span", { class: "muted small" }, `${when(m.created)} · 用过 ${m.used} 次`)),
              h("p", null, m.content),
              h("div", { class: "mem-actions" },
                tab === "pending" && h("button", { class: "btn primary sm", onclick: () => void approveMemory(m.id) }, "记住它"),
                h("button", { class: "btn ghost sm", onclick: () => void forgetMemory(m.id) }, "忘掉")))))));
}
