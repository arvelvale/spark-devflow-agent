import { createElement, type IconNode } from "lucide";

export type Child = Node | string | number | null | undefined | false | Child[];
type Props = {
  class?: string | (string | false | null | undefined)[];
  style?: string;
  title?: string;
  dataset?: Record<string, string>;
  attrs?: Record<string, string | boolean | undefined>;
  [on: `on${string}`]: ((ev: any) => void) | undefined;
};

/** 小型 hyperscript：h("div", {class: "x", onclick}, 子节点...) */
export function h<K extends keyof HTMLElementTagNameMap>(tag: K, props?: Props | null, ...children: Child[]): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  if (props) {
    for (const [key, value] of Object.entries(props)) {
      if (value === undefined || value === null) continue;
      if (key === "class") {
        el.className = Array.isArray(value) ? value.filter(Boolean).join(" ") : String(value);
      } else if (key === "style") {
        el.setAttribute("style", String(value));
      } else if (key === "title") {
        el.title = String(value);
      } else if (key === "dataset") {
        Object.assign(el.dataset, value);
      } else if (key === "attrs") {
        for (const [a, v] of Object.entries(value as Record<string, unknown>)) {
          if (v === false || v === undefined) continue;
          el.setAttribute(a, v === true ? "" : String(v));
        }
      } else if (key.startsWith("on") && typeof value === "function") {
        el.addEventListener(key.slice(2).toLowerCase(), value as EventListener);
      }
    }
  }
  append(el, children);
  return el;
}

function append(parent: Node, children: Child[]): void {
  for (const c of children) {
    if (c === null || c === undefined || c === false) continue;
    if (Array.isArray(c)) append(parent, c);
    else parent.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(String(c)) : c);
  }
}

export function icon(node: IconNode, size = 16, cls = ""): SVGElement {
  const svg = createElement(node, { width: size, height: size, "stroke-width": 1.75 });
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("icon");
  if (cls) svg.classList.add(...cls.split(" "));
  return svg;
}

/** 把容器内容换成新节点（整块重绘，面板规模小，不做细粒度 diff） */
export function mount(container: HTMLElement, ...nodes: Child[]): void {
  container.replaceChildren();
  append(container, nodes);
}
