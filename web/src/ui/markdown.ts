import DOMPurify from "dompurify";
import { marked } from "marked";
import { h } from "./dom";

marked.setOptions({ gfm: true, breaks: true });
const cache = new Map<string, string>();

/** 模型输出一律当不可信内容：渲染 Markdown 后再过一遍 DOMPurify */
export function markdown(text: string): HTMLElement {
  let html = cache.get(text);
  if (html === undefined) {
    html = DOMPurify.sanitize(marked.parse(text, { async: false }) as string, { USE_PROFILES: { html: true } });
    if (cache.size > 300) cache.clear();
    cache.set(text, html);
  }
  const el = h("div", { class: "md" });
  el.innerHTML = html;
  el.querySelectorAll("a").forEach((a) => {
    a.setAttribute("target", "_blank");
    a.setAttribute("rel", "noopener noreferrer");
  });
  return el;
}
