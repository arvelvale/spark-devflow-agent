import { rng } from "./random";

/** 程序化纸张：暖白底 + 大块浅斑 + 短纤维 + 颗粒 + 四角压暗。只生成一次，每帧直接贴。 */
export function makePaper(w: number, h: number): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const g = c.getContext("2d")!;
  const r = rng(2026);
  g.fillStyle = "#f3ecdd";
  g.fillRect(0, 0, w, h);
  for (let i = 0; i < 40; i++) {
    const x = r() * w, y = r() * h, rad = 180 + r() * 620;
    const gr = g.createRadialGradient(x, y, 0, x, y, rad);
    gr.addColorStop(0, `rgba(170, 140, 96, ${0.025 + r() * 0.045})`);
    gr.addColorStop(1, "rgba(170, 140, 96, 0)");
    g.fillStyle = gr;
    g.fillRect(x - rad, y - rad, rad * 2, rad * 2);
  }
  g.lineCap = "round";
  for (let i = 0; i < 3200; i++) {
    const x = r() * w, y = r() * h, a = r() * Math.PI * 2, l = 4 + r() * 20;
    g.strokeStyle = `rgba(120, 92, 58, ${0.025 + r() * 0.06})`;
    g.lineWidth = 0.5 + r() * 0.7;
    g.beginPath();
    g.moveTo(x, y);
    g.quadraticCurveTo(x + Math.cos(a + 0.6) * l * 0.5, y + Math.sin(a + 0.6) * l * 0.5, x + Math.cos(a) * l, y + Math.sin(a) * l);
    g.stroke();
  }
  const im = g.getImageData(0, 0, w, h), d = im.data;
  for (let i = 0; i < d.length; i += 4) {
    const n = (r() - 0.5) * 12 + (r() < 0.006 ? -30 * r() : 0);
    d[i] += n;
    d[i + 1] += n;
    d[i + 2] += n * 0.9;
  }
  g.putImageData(im, 0, 0);
  const v = g.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.35, w / 2, h / 2, Math.max(w, h) * 0.75);
  v.addColorStop(0, "rgba(90, 64, 30, 0)");
  v.addColorStop(1, "rgba(90, 64, 30, 0.16)");
  g.fillStyle = v;
  g.fillRect(0, 0, w, h);
  return c;
}
