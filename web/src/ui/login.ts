import { KeyRound, Radio } from "lucide";
import { login } from "../store";
import { h, icon } from "./dom";

export function renderLogin(): HTMLElement {
  const input = h("input", {
    class: "input", attrs: { type: "password", placeholder: "访问口令", autocomplete: "current-password", autofocus: true },
  });
  const err = h("div", { class: "login-error" });
  const btn = h("button", { class: "btn primary block", attrs: { type: "submit" } }, "进入面板");
  const form = h("form", {
    class: "login-card",
    onsubmit: async (e: Event) => {
      e.preventDefault();
      if (!input.value.trim()) {
        err.textContent = "先填一下口令";
        return;
      }
      btn.setAttribute("disabled", "");
      btn.textContent = "正在验证…";
      const msg = await login(input.value);
      btn.removeAttribute("disabled");
      btn.textContent = "进入面板";
      if (msg) err.textContent = msg === "访问口令不对" ? "口令不太对，再对一下终端里打印的那一串" : msg;
    },
  },
  h("div", { class: "brand-mark lg" }, icon(Radio, 22)),
  h("h1", null, "Spark 开发流"),
  h("p", { class: "login-sub" }, "口令在启动面板的终端里，形如「访问口令：xxxx」"),
  h("label", { class: "input-wrap" }, icon(KeyRound, 16), input),
  err,
  btn);
  setTimeout(() => input.focus(), 0);
  return h("div", { class: "login" }, form);
}
