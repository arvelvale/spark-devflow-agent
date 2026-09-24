// 生成配音：逐句调阶跃 TTS → 拼成一条配音轨 + 时间清单。
//   node scripts/tts.mjs              只生成缺的句子（按"音色+文本"哈希缓存）
//   VOICE=cixingnansheng node scripts/tts.mjs   换音色
// 密钥只从环境变量 STEPFUN_API_KEY 或仓库根 .env 读，不会写进任何产物。
// 产物：public/audio/narration.mp3 + public/audio/manifest.json（画面按这里的时间点对齐每一句）
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const SCRIPT = JSON.parse(fs.readFileSync(path.join(ROOT, "src/script.json"), "utf8"));
const CACHE = path.join(ROOT, ".tts-cache");
const OUT = path.join(ROOT, "public/audio");
const VOICE = process.env.VOICE || SCRIPT.voice;
const BASE = process.env.STEPFUN_BASE || "https://api.stepfun.com/step_plan/v1";
const RATE = 24000;
// 节奏（秒）：每章开头留白、句间停顿、章末留白（画面在这段时间收尾和转场）
const LEAD = 0.6, GAP = 0.45, TAIL = 1.1;

function key() {
  if (process.env.STEPFUN_API_KEY) return process.env.STEPFUN_API_KEY;
  const env = path.resolve(ROOT, "../.env");
  if (fs.existsSync(env)) {
    for (const line of fs.readFileSync(env, "utf8").split(/\r?\n/)) {
      const m = line.match(/^STEPFUN_API_KEY=(.+)$/);
      if (m) return m[1].trim();
    }
  }
  throw new Error("没有找到 STEPFUN_API_KEY（环境变量或仓库根 .env）");
}

/** 走 RIFF 块找出 PCM 数据（阶跃返回的 WAV 在 data 块后面还有别的块） */
function pcmOf(buf) {
  if (buf.toString("ascii", 0, 4) !== "RIFF") throw new Error("不是 WAV");
  let off = 12, fmt = null;
  while (off + 8 <= buf.length) {
    const id = buf.toString("ascii", off, off + 4), size = buf.readUInt32LE(off + 4);
    if (id === "fmt ") fmt = { ch: buf.readUInt16LE(off + 10), rate: buf.readUInt32LE(off + 12), bits: buf.readUInt16LE(off + 22) };
    if (id === "data") {
      if (!fmt || fmt.ch !== 1 || fmt.rate !== RATE || fmt.bits !== 16) throw new Error(`格式不符：${JSON.stringify(fmt)}`);
      return buf.subarray(off + 8, off + 8 + size);
    }
    off += 8 + size + (size % 2);
  }
  throw new Error("WAV 里没有 data 块");
}

async function synth(text, apiKey) {
  for (let attempt = 0; attempt < 5; attempt++) {
    const r = await fetch(`${BASE}/audio/speech`, {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({ model: "stepaudio-2.5-tts", input: text, voice: VOICE, response_format: "wav" }),
    });
    if (r.ok) return Buffer.from(await r.arrayBuffer());
    if (r.status === 429 || r.status >= 500) {
      await new Promise((ok) => setTimeout(ok, 1500 * 2 ** attempt));
      continue;
    }
    throw new Error(`TTS 失败 HTTP ${r.status}: ${(await r.text()).slice(0, 200)}`);
  }
  throw new Error("TTS 重试耗尽");
}

const silence = (sec) => Buffer.alloc(Math.round(sec * RATE) * 2);

async function main() {
  fs.mkdirSync(CACHE, { recursive: true });
  fs.mkdirSync(OUT, { recursive: true });
  const apiKey = key();
  const jobs = [];
  for (const s of SCRIPT.scenes)
    for (const text of s.lines) {
      const h = crypto.createHash("sha1").update(`${VOICE}\n${text}`).digest("hex").slice(0, 16);
      jobs.push({ text, file: path.join(CACHE, `${h}.wav`) });
    }
  const todo = jobs.filter((j) => !fs.existsSync(j.file));
  console.log(`音色 ${VOICE}：共 ${jobs.length} 句，需要生成 ${todo.length} 句`);
  let done = 0;
  const worker = async () => {
    while (todo.length) {
      const j = todo.shift();
      fs.writeFileSync(j.file, await synth(j.text, apiKey));
      console.log(`  ${++done}. ${j.text.slice(0, 24)}…`);
    }
  };
  await Promise.all([worker(), worker(), worker()]); // 阶跃并发约 8 就 429，留余量

  const parts = [], manifest = { voice: VOICE, rate: RATE, scenes: [] };
  let t = 0, i = 0;
  const push = (buf) => { parts.push(buf); t += buf.length / 2 / RATE; };
  for (const s of SCRIPT.scenes) {
    const scene = { id: s.id, title: s.title, start: +t.toFixed(3), lines: [] };
    push(silence(LEAD));
    s.lines.forEach((text, k) => {
      if (k > 0) push(silence(GAP));
      const pcm = pcmOf(fs.readFileSync(jobs[i++].file));
      const start = t;
      push(pcm);
      scene.lines.push({ text, start: +start.toFixed(3), end: +t.toFixed(3) });
    });
    push(silence(TAIL));
    scene.end = +t.toFixed(3);
    manifest.scenes.push(scene);
  }
  manifest.total = +t.toFixed(3);
  const pcm = Buffer.concat(parts), header = Buffer.alloc(44);
  header.write("RIFF", 0); header.writeUInt32LE(36 + pcm.length, 4); header.write("WAVE", 8);
  header.write("fmt ", 12); header.writeUInt32LE(16, 16); header.writeUInt16LE(1, 20); header.writeUInt16LE(1, 22);
  header.writeUInt32LE(RATE, 24); header.writeUInt32LE(RATE * 2, 28); header.writeUInt16LE(2, 32); header.writeUInt16LE(16, 34);
  header.write("data", 36); header.writeUInt32LE(pcm.length, 40);
  const wav = path.join(CACHE, "narration.wav");
  fs.writeFileSync(wav, Buffer.concat([header, pcm]));
  // 压成 mp3 放进 public（wav 太大，只留在缓存里）
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", wav, "-ac", "1", "-b:a", "64k", path.join(OUT, "narration.mp3")]);
  fs.writeFileSync(path.join(OUT, "manifest.json"), JSON.stringify(manifest, null, 2));
  console.log(`完成：总长 ${manifest.total.toFixed(1)} 秒 → public/audio/narration.mp3 + manifest.json`);
}

main().catch((e) => { console.error(e.message); process.exit(1); });
