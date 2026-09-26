import { Menu, PanelRight } from "lucide";
import "./styles.css";
import { checkAuth, loadStatus, openSession, setTier, state, subscribe, update } from "./store";
import { renderMessages } from "./ui/chat";
import { createComposer } from "./ui/composer";
import { h, icon, mount } from "./ui/dom";
import { renderDrawer } from "./ui/drawer";
import { renderLogin } from "./ui/login";
import { createModelSettings } from "./ui/models";
import { renderSidebar } from "./ui/sidebar";
import { renderTracePanel } from "./ui/trace";

const root = document.getElementById("app")!;

// 布局骨架只建一次；各区域在状态变化时整块重绘（输入框除外，见 composer.ts）
const sidebar = h("aside", { class: "sidebar" });
const header = h("header", { class: "chat-head" });
const messages = h("div", { class: "messages" });
const composer = createComposer();
const modelSettings = createModelSettings();
let lastDrawer: string | null = null;
const panel = h("aside", { class: "panel" });
const overlay = h("div", { class: "overlay-root" });
const toastBox = h("div", { class: "toast-root", attrs: { "aria-live": "polite" } });
const shell = h("div", { class: "shell" },
  sidebar,
  h("main", { class: "chat" }, header, messages, composer.el),
  panel,
  overlay,
  toastBox);

function renderHeader(): (HTMLElement | null)[] {
  const cur = state.current;
  const title = cur ? (state.sessions.find((x) => x.id === cur.id)?.title ?? "新对话") : "Spark 开发流";
  const tierSelect = cur?.live
    ? h("div", { class: "seg small" },
        ["auto", "local", "cloud"].map((t) => h("button", {
          class: ["seg-btn", cur.tier === t && "on"], title: "模型档位（下一轮生效）", onclick: () => void setTier(t),
        }, { auto: "自动", local: "主力", cloud: "难题" }[t]!)))
    : null;
  return [
    h("button", { class: "icon-btn only-mobile", title: "会话列表", onclick: () => update((s) => (s.sidebarOpen = true)) }, icon(Menu, 18)),
    h("div", { class: "chat-title" },
      h("span", { class: "title-text" }, title),
      cur && h("span", { class: `badge ${cur.useJev === false ? "" : "accent"}` },
        cur.useJev === false ? "基线 · 无 JEV" : cur.live ? "JEV 决策层" : "历史回放")),
    tierSelect,
    h("button", {
      class: ["icon-btn only-narrow", state.mobileView === "trace" && "on"], title: "决策轨迹",
      onclick: () => update((s) => (s.mobileView = s.mobileView === "trace" ? "chat" : "trace")),
    }, icon(PanelRight, 18)),
  ];
}

let lastTurnCount = -1;

function render(): void {
  if (state.authed === null) {
    mount(root, h("div", { class: "boot" }, "正在连接面板…"));
    return;
  }
  if (!state.authed) {
    if (!root.querySelector(".login")) mount(root, renderLogin());
    return;
  }
  if (!root.contains(shell)) mount(root, shell);
  shell.classList.toggle("sidebar-open", state.sidebarOpen);
  shell.classList.toggle("show-trace", state.mobileView === "trace");

  // 重绘前记住是否贴着底部，重绘后保持
  const nearBottom = messages.scrollHeight - messages.scrollTop - messages.clientHeight < 80;
  const panelScroll = panel.querySelector(".panel-scroll")?.scrollTop ?? 0;
  mount(sidebar, renderSidebar());
  mount(header, ...renderHeader());
  mount(messages, renderMessages());
  mount(panel, renderTracePanel());
  const ps = panel.querySelector(".panel-scroll");
  if (ps) ps.scrollTop = panelScroll;
  const turnCount = state.current?.turns.size ?? 0;
  if (nearBottom || turnCount !== lastTurnCount) messages.scrollTop = messages.scrollHeight;
  lastTurnCount = turnCount;
  // 模型设置里有输入框，只在打开时挂一次，之后的全局重绘不碰它
  if (state.drawer === "models") {
    if (lastDrawer !== "models") {
      modelSettings.open();
      mount(overlay, modelSettings.el);
    }
  } else {
    mount(overlay, renderDrawer());
  }
  lastDrawer = state.drawer;
  mount(toastBox, state.toast && h("div", { class: `toast ${state.toast.kind}` }, state.toast.text));
  composer.sync();
}

subscribe(render);
render();

void checkAuth().then(async () => {
  if (!state.authed) return;
  const fromHash = decodeURIComponent(location.hash.slice(1));
  const target = state.sessions.find((x) => x.id === fromHash) ?? state.sessions.find((x) => x.live);
  if (target) await openSession(target.id);
});

// 服务状态每 30 秒刷新一次（本地模型可能被重启）
window.setInterval(() => state.authed && void loadStatus(), 30_000);
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") update((s) => { s.drawer = null; s.newSessionOpen = false; s.sidebarOpen = false; });
});
