import { Check, ChevronLeft, CircleAlert, Globe, KeyRound, LoaderCircle, Lock, Plus, RefreshCw, Route, Trash2, X, Zap } from "lucide";
import { api, ApiError } from "../api";
import { loadStatus, toast, update } from "../store";
import type { ModelsView, Preset, ProviderView, Slot } from "../types";
import { h, icon, mount } from "./dom";

const SLOTS: { key: Slot; label: string; hint: string }[] = [
  { key: "local", label: "主力", hint: "日常任务都交给它；是私有模型时，摘要和记忆整理也由它来做" },
  { key: "backup", label: "备用", hint: "主力连不上时顶上" },
  { key: "cloud", label: "难题", hint: "JEV 判断为难题，或主力连续出错时升级到它" },
];

interface Draft {
  isNew: boolean;
  id: string;
  name: string;
  baseUrl: string;
  apiKey: string;
  clearKey: boolean;
  private: boolean;
  useProxy: boolean;
  models: string;
  hasKey: boolean;
  keySource: ProviderView["key_source"];
  keyEnv: string;
}

type TestState = { model: string; busy: boolean; text?: string; ok?: boolean };

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 32);
const errText = (e: unknown) => (e instanceof ApiError ? e.message : "出了点意外，稍后再试一次");

/**
 * 模型设置抽屉。里面有输入框，所以和输入区一样只建一次、自己管理重绘
 * （全局重绘会让正在填的 Key 和地址丢掉）。open() 时从后端重新拉一次。
 */
export function createModelSettings(): { el: HTMLElement; open: () => void } {
  let view: ModelsView | null = null;
  let draft: Draft | null = null;
  let picking = false;          // 正在选预设
  let saving = false;
  let discovered: string[] = [];
  let discovering = false;
  let test: TestState | null = null;
  let loadError = "";

  const body = h("div", { class: "drawer-body" });
  const title = h("h3", null, "模型设置");
  const sub = h("p", { class: "muted small" });
  const close = () => update((s) => (s.drawer = null));
  const el = h("div", { class: "drawer-mask", onclick: (e: MouseEvent) => e.target === e.currentTarget && close() },
    h("aside", { class: "drawer wide", attrs: { role: "dialog", "aria-label": "模型设置" } },
      h("header", { class: "drawer-head" }, h("div", null, title, sub),
        h("button", { class: "icon-btn", title: "关闭", onclick: close }, icon(X, 16))),
      body));

  async function refresh() {
    try {
      view = await api.models();
      loadError = "";
    } catch (e) {
      loadError = errText(e);
    }
    render();
  }

  function applied(v: ModelsView, msg: string) {
    view = v;
    toast(msg);
    void loadStatus();
  }

  // ---------------- 列表页 ----------------
  function slotRow(key: Slot, label: string, hint: string): HTMLElement {
    const ref = view!.slots[key];
    const current = ref ? `${ref.provider}\u0000${ref.model}` : "";
    const prov = view!.providers.find((p) => p.id === ref?.provider);
    const select = h("select", {
      class: "select",
      attrs: { "aria-label": `${label}模型` },
      onchange: async (e: Event) => {
        const [provider, model] = (e.target as HTMLSelectElement).value.split("\u0000");
        try {
          applied(await api.setSlots({ [key]: { provider, model } }), `「${label}」已换成 ${model}，新对话生效`);
        } catch (err) {
          toast(errText(err), "error");
        }
        render();
      },
    },
    view!.providers.map((p) => h("optgroup", { attrs: { label: p.name } },
      p.models.map((m) => {
        const o = h("option", { attrs: { value: `${p.id}\u0000${m.name}` } }, m.name);
        o.selected = `${p.id}\u0000${m.name}` === current;
        return o;
      }))));
    return h("div", { class: "slot-row" },
      h("div", { class: "slot-text" },
        h("div", { class: "slot-label" }, label, prov && privacyTag(prov)),
        h("div", { class: "muted small" }, hint)),
      select);
  }

  function privacyTag(p: ProviderView): HTMLElement {
    return p.private
      ? h("span", { class: "tag accent", title: "部署在自己的机器上：可以看到隐私记忆" }, icon(Lock, 11), "私有")
      : h("span", { class: "tag cloud", title: "外部服务：隐私记忆不会发给它" }, icon(Globe, 11), "外部");
  }

  function keyTag(p: ProviderView): HTMLElement | null {
    if (p.private && !p.has_key) return null;
    if (!p.has_key) return h("span", { class: "tag warn" }, icon(CircleAlert, 11), "未填 Key");
    return h("span", { class: "tag", title: p.key_source === "env" ? `来自 .env 的 ${p.key_env}` : "在面板里填写" },
      icon(KeyRound, 11), p.key_source === "env" ? "Key · .env" : "Key · 已保存");
  }

  function providerCard(p: ProviderView): HTMLElement {
    const inUse = SLOTS.filter((s) => view!.slots[s.key]?.provider === p.id).map((s) => s.label);
    return h("button", { class: "prov-card", onclick: () => edit(p) },
      h("div", { class: "prov-top" },
        h("span", { class: "prov-name" }, p.name),
        privacyTag(p), keyTag(p),
        p.use_proxy && h("span", { class: "tag", title: "经操作机代理出境（节点直连不了境外）" }, icon(Route, 11), "代理"),
        inUse.length > 0 && h("span", { class: "muted small in-use" }, `用于 ${inUse.join("、")}`)),
      h("div", { class: "prov-url mono" }, p.base_url),
      h("div", { class: "chips" }, p.models.map((m) => h("span", { class: "chip" }, m.name))));
  }

  function presetPicker(): HTMLElement {
    const taken = new Set(view!.providers.map((p) => p.id));
    const custom: Preset = { id: "", name: "自定义", base_url: "" };
    return h("div", { class: "preset-box" },
      h("div", { class: "preset-head" }, h("span", null, "选一个起点"),
        h("button", { class: "btn ghost sm", onclick: () => { picking = false; render(); } }, "取消")),
      h("div", { class: "preset-grid" },
        [...view!.presets, custom].map((pr) => h("button", {
          class: "preset", attrs: { disabled: pr.id !== "" && taken.has(pr.id) },
          title: pr.id && taken.has(pr.id) ? "已经添加过了" : pr.base_url,
          onclick: () => startNew(pr),
        }, pr.name))));
  }

  function listPage(): HTMLElement[] {
    const v = view!;
    return [
      h("section", { class: "set-section" },
        h("div", { class: "set-title" }, "分工"),
        h("div", { class: "slot-list" }, SLOTS.map((s) => slotRow(s.key, s.label, s.hint))),
        h("p", { class: "muted small note" }, "切换后新建的对话生效；进行中的对话继续用原来的模型。")),
      h("section", { class: "set-section" },
        h("div", { class: "set-title" }, "供应商",
          !picking && h("button", { class: "btn sm", onclick: () => { picking = true; render(); } }, icon(Plus, 14), "添加")),
        picking && presetPicker(),
        h("div", { class: "prov-list" }, v.providers.map(providerCard))),
      h("p", { class: "muted small note" }, icon(Lock, 12),
        " Key 只保存在节点上的 var/models.json，保存后不会再显示出来。所有供应商都按 OpenAI 兼容接口调用。"),
    ];
  }

  // ---------------- 编辑页 ----------------
  function edit(p: ProviderView) {
    draft = {
      isNew: false, id: p.id, name: p.name, baseUrl: p.base_url, apiKey: "", clearKey: false,
      private: p.private, useProxy: p.use_proxy, models: p.models.map((m) => m.name).join("\n"),
      hasKey: p.has_key, keySource: p.key_source, keyEnv: p.key_env,
    };
    discovered = [];
    test = null;
    render();
  }

  function startNew(pr: Preset) {
    const taken = new Set(view!.providers.map((p) => p.id));
    let id = pr.id || "custom";
    for (let i = 2; taken.has(id); i++) id = `${pr.id || "custom"}-${i}`;
    draft = {
      isNew: true, id, name: pr.id ? pr.name : "", baseUrl: pr.base_url, apiKey: "", clearKey: false,
      private: !!pr.private, useProxy: !!pr.use_proxy, models: "", hasKey: false, keySource: null, keyEnv: "",
    };
    picking = false;
    discovered = [];
    test = null;
    render();
  }

  const modelNames = () => [...new Set(draft!.models.split(/[\n,]/).map((s) => s.trim()).filter(Boolean))];

  async function save() {
    const d = draft!;
    if (d.isNew && !d.id) d.id = slug(d.name) || "custom";
    saving = true;
    render();
    try {
      const v = await api.saveProvider(d.id, {
        name: d.name.trim() || d.id, base_url: d.baseUrl.trim(), private: d.private, use_proxy: d.useProxy,
        models: modelNames().map((name) => ({ name })),
        ...(d.apiKey.trim() ? { api_key: d.apiKey.trim() } : d.clearKey ? { api_key: "" } : {}),
      });
      applied(v, `已保存「${d.name || d.id}」`);
      const p = v.providers.find((x) => x.id === d.id);
      if (p) edit(p);  // 留在编辑页，方便接着拉模型、测连通
    } catch (e) {
      toast(errText(e), "error");
    } finally {
      saving = false;
      render();
    }
  }

  async function remove() {
    const d = draft!;
    if (!window.confirm(`删除「${d.name || d.id}」？它保存的 Key 也会一起删掉。`)) return;
    try {
      applied(await api.deleteProvider(d.id), `已删除「${d.name || d.id}」`);
      draft = null;
    } catch (e) {
      toast(errText(e), "error");
    }
    render();
  }

  async function discover() {
    discovering = true;
    render();
    try {
      const names = new Set(modelNames());
      discovered = (await api.discoverModels(draft!.id)).models.filter((m) => !names.has(m));
      if (!discovered.length) toast("接口里的模型都已经在列表里了");
    } catch (e) {
      toast(errText(e), "error");
    } finally {
      discovering = false;
      render();
    }
  }

  async function runTest(model: string) {
    test = { model, busy: true };
    render();
    try {
      const r = await api.testModel(draft!.id, model);
      test = r.ok
        ? { model, busy: false, ok: true, text: `在线 · ${r.latency_ms} ms · 「${r.reply ?? ""}」` }
        : { model, busy: false, ok: false, text: r.error ?? "失败" };
    } catch (e) {
      test = { model, busy: false, ok: false, text: errText(e) };
    }
    render();
  }

  function field(label: string, input: HTMLElement, hint?: string | HTMLElement): HTMLElement {
    return h("label", { class: "field" }, h("span", { class: "field-label" }, label), input,
      hint && h("span", { class: "field-hint" }, hint));
  }

  function text(key: "name" | "baseUrl" | "apiKey" | "id" | "models", attrs: Record<string, string>, area = false) {
    const node = area ? h("textarea", { class: "text-input area", attrs }) : h("input", { class: "text-input", attrs });
    (node as HTMLInputElement).value = draft![key];
    node.addEventListener("input", () => { draft![key] = (node as HTMLInputElement).value; });
    return node;
  }

  function toggle(key: "private" | "useProxy", label: string, hint: string): HTMLElement {
    const on = draft![key];
    return h("div", { class: "toggle-row" },
      h("div", null, h("div", { class: "field-label" }, label), h("div", { class: "field-hint" }, hint)),
      h("button", {
        class: ["switch", on && "on"], attrs: { role: "switch", "aria-checked": String(on), type: "button", "aria-label": label },
        onclick: () => { draft![key] = !draft![key]; render(); },
      }, h("span", { class: "knob" })));
  }

  function editPage(): HTMLElement[] {
    const d = draft!;
    const keyHint = d.clearKey
      ? "保存后清除面板里的 Key" + (d.keyEnv ? `，改用 .env 的 ${d.keyEnv}` : "")
      : d.keySource === "panel"
        ? h("span", null, "已保存。留空保持不变，填新的会覆盖。 ",
            h("button", { class: "link", attrs: { type: "button" }, onclick: () => { d.clearKey = true; d.apiKey = ""; render(); } }, "清除"))
        : d.keySource === "env" ? `当前用 .env 的 ${d.keyEnv}；在这里填写会优先使用` : "本机服务一般不需要 Key";
    const saved = !d.isNew;
    return [
      h("button", { class: "back", onclick: () => { draft = null; void refresh(); } }, icon(ChevronLeft, 16), "返回"),
      h("div", { class: "form" },
        field("名称", text("name", { placeholder: "比如 DeepSeek", maxlength: "40" })),
        d.isNew && field("编号", text("id", { placeholder: "小写字母、数字、连字符", maxlength: "32", spellcheck: "false" }),
          "保存后不能改，分工和日志里用它来指代这个供应商"),
        field("接口地址", text("baseUrl", { placeholder: "https://…/v1", spellcheck: "false", inputmode: "url" }),
          "OpenAI 兼容接口的根地址，一般以 /v1 结尾。改了地址需要重新填 Key"),
        field("API Key", text("apiKey", {
          type: "password", autocomplete: "off", spellcheck: "false",
          placeholder: d.hasKey && !d.clearKey ? "已设置" : "sk-…",
        }), keyHint),
        field("模型", text("models", { rows: "4", placeholder: "每行一个模型名", spellcheck: "false" }, true),
          saved ? h("span", null,
            h("button", { class: "link", attrs: { type: "button", disabled: discovering }, onclick: () => void discover() },
              icon(discovering ? LoaderCircle : RefreshCw, 12, discovering ? "spin" : ""), " 从接口拉取"),
            "　或手动填写")
            : "先保存，再从接口拉取模型列表"),
        discovered.length > 0 && h("div", { class: "chips pick" },
          discovered.slice(0, 60).map((m) => h("button", {
            class: "chip add", title: "加入列表",
            onclick: () => { d.models = [...modelNames(), m].join("\n"); discovered = discovered.filter((x) => x !== m); render(); },
          }, icon(Plus, 11), m))),
        toggle("private", "私有部署", "模型跑在自己控制的机器上。只有私有模型能看到隐私记忆、做摘要和记忆整理"),
        toggle("useProxy", "经操作机代理出境", "节点直连不了境外。OpenAI、Anthropic 这类境外服务要打开"),
        saved && modelNames().length > 0 && h("div", { class: "test-box" },
          h("div", { class: "field-label" }, "测试连通"),
          h("div", { class: "chips" }, modelNames().map((m) => h("button", {
            class: ["chip", "test", test?.model === m && "on"], attrs: { disabled: !!test?.busy },
            onclick: () => void runTest(m),
          }, icon(test?.model === m && test.busy ? LoaderCircle : Zap, 11, test?.model === m && test.busy ? "spin" : ""), m))),
          test && !test.busy && h("div", { class: ["test-result", test.ok ? "ok" : "bad"] },
            icon(test.ok ? Check : CircleAlert, 13), test.text ?? ""),
          h("div", { class: "field-hint" }, "测的是已保存的设置；改了先保存再测")),
        h("div", { class: "form-actions" },
          saved && h("button", { class: "btn ghost danger", onclick: () => void remove() }, icon(Trash2, 14), "删除"),
          h("span", { class: "spacer" }),
          h("button", { class: "btn ghost", onclick: () => { draft = null; void refresh(); } }, "取消"),
          h("button", { class: "btn primary", attrs: { disabled: saving }, onclick: () => void save() },
            saving ? "保存中…" : "保存"))),
    ];
  }

  function render() {
    if (draft) {
      title.textContent = draft.isNew ? "添加供应商" : draft.name || draft.id;
      sub.textContent = draft.isNew ? "填好地址和 Key，保存后可以拉取模型、测试连通" : "修改后点保存；新建的对话生效";
      mount(body, ...editPage());
      return;
    }
    title.textContent = "模型设置";
    sub.textContent = "登记你自己的模型服务，再给主力、备用、难题各选一个。";
    if (loadError) mount(body, h("p", { class: "muted drawer-empty" }, loadError));
    else if (!view) mount(body, h("p", { class: "muted drawer-empty" }, "正在读取…"));
    else mount(body, ...listPage());
  }

  return {
    el,
    open() {
      draft = null;
      picking = false;
      render();
      void refresh();
    },
  };
}
