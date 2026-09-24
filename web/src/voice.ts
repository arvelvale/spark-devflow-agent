// 语音输入：MediaRecorder 录音 → 浏览器里解码并重采样成 16 kHz 单声道 WAV → 后端转发阶跃 ASR。
// 在前端转 WAV，是因为各浏览器录出来的容器格式不一样（webm/ogg/mp4），WAV 阶跃一定认。
// 注意：浏览器只在安全上下文（https 或 localhost）里开放麦克风；经公网 http 打开时语音不可用。

const TARGET_RATE = 16000;
export const MAX_SECONDS = 60;

export function voiceSupported(): { ok: boolean; reason?: string } {
  if (!window.isSecureContext) return { ok: false, reason: "语音需要通过 localhost 或 https 打开面板" };
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined")
    return { ok: false, reason: "这个浏览器不支持录音" };
  return { ok: true };
}

export class Recorder {
  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private ctx: AudioContext | null = null;
  private raf = 0;

  /** onLevel 回调 0..1 的音量，用来画录音动效 */
  async start(onLevel: (v: number) => void): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true } });
    this.chunks = [];
    this.recorder = new MediaRecorder(this.stream);
    this.recorder.ondataavailable = (e) => e.data.size && this.chunks.push(e.data);
    this.recorder.start(250);
    this.ctx = new AudioContext();
    const analyser = this.ctx.createAnalyser();
    analyser.fftSize = 512;
    this.ctx.createMediaStreamSource(this.stream).connect(analyser);
    const buf = new Uint8Array(analyser.fftSize);
    const tick = () => {
      analyser.getByteTimeDomainData(buf);
      let peak = 0;
      for (const b of buf) peak = Math.max(peak, Math.abs(b - 128));
      onLevel(Math.min(1, peak / 64));
      this.raf = requestAnimationFrame(tick);
    };
    tick();
  }

  async stop(): Promise<Blob> {
    const rec = this.recorder;
    if (!rec) throw new Error("没有在录音");
    const stopped = new Promise<void>((resolve) => (rec.onstop = () => resolve()));
    rec.stop();
    await stopped;
    this.cleanup();
    const blob = new Blob(this.chunks, { type: rec.mimeType || "audio/webm" });
    return toWav16k(blob);
  }

  cancel(): void {
    try {
      this.recorder?.stop();
    } catch {
      /* 已经停了 */
    }
    this.cleanup();
  }

  private cleanup(): void {
    cancelAnimationFrame(this.raf);
    this.stream?.getTracks().forEach((t) => t.stop());
    void this.ctx?.close();
    this.stream = null;
    this.recorder = null;
    this.ctx = null;
  }
}

async function toWav16k(blob: Blob): Promise<Blob> {
  const data = await blob.arrayBuffer();
  const decodeCtx = new AudioContext();
  const decoded = await decodeCtx.decodeAudioData(data);
  void decodeCtx.close();
  const frames = Math.max(1, Math.ceil(decoded.duration * TARGET_RATE));
  const offline = new OfflineAudioContext(1, frames, TARGET_RATE);
  const src = offline.createBufferSource();
  src.buffer = decoded;
  src.connect(offline.destination);
  src.start();
  const rendered = await offline.startRendering();
  return encodeWav(rendered.getChannelData(0), TARGET_RATE);
}

export function encodeWav(samples: Float32Array, rate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeStr = (off: number, s: string) => [...s].forEach((c, i) => view.setUint8(off + i, c.charCodeAt(0)));
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true); // fmt 块长度
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // 单声道
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true); // 字节率
  view.setUint16(32, 2, true); // 块对齐
  view.setUint16(34, 16, true); // 位深
  writeStr(36, "data");
  view.setUint32(40, samples.length * 2, true);
  let off = 44;
  for (const s of samples) {
    const v = Math.max(-1, Math.min(1, s));
    view.setInt16(off, v < 0 ? v * 0x8000 : v * 0x7fff, true);
    off += 2;
  }
  return new Blob([buffer], { type: "audio/wav" });
}
