import { ArrowUp, LoaderCircle, Mic, Square } from "lucide";
import { api, ApiError } from "../api";
import { sendTurn, state, toast } from "../store";
import { MAX_SECONDS, Recorder, voiceSupported } from "../voice";
import { h, icon, mount } from "./dom";

type VoiceState = "idle" | "recording" | "transcribing";

/** 输入框只建一次（重绘会丢焦点和输入法状态），状态变化时调用 sync() */
export function createComposer(): { el: HTMLElement; sync: () => void } {
  let voice: VoiceState = "idle";
  let voiceDraft = false; // 当前文字来自语音识别（用户没清空之前都算语音输入）
  let recorder: Recorder | null = null;
  let timer = 0;
  let seconds = 0;

  const textarea = h("textarea", {
    class: "composer-input",
    attrs: { rows: "1", placeholder: "说说要做什么，比如「把 DAY-298 拆一下」", "aria-label": "输入" },
  });
  const micBtn = h("button", { class: "icon-btn mic", attrs: { type: "button" } });
  const sendBtn = h("button", { class: "send", attrs: { type: "button", "aria-label": "发送" } }, icon(ArrowUp, 18));
  const hint = h("div", { class: "composer-hint" });
  const level = h("span", { class: "level" });

  const autosize = () => {
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 220)}px`;
  };

  const busy = () => !state.current?.live || !!state.current?.busy;

  async function submit() {
    const text = textarea.value.trim();
    if (!text || busy() || voice !== "idle") return;
    const ok = await sendTurn(text, voiceDraft ? "voice" : "text");
    if (ok) {
      textarea.value = "";
      voiceDraft = false;
      autosize();
    }
    sync();
  }

  async function toggleVoice() {
    const support = voiceSupported();
    if (!support.ok) {
      toast(support.reason!, "info");
      return;
    }
    if (voice === "idle") {
      recorder = new Recorder();
      try {
        await recorder.start((v) => level.style.setProperty("--lv", String(v)));
      } catch {
        recorder = null;
        toast("没拿到麦克风权限，可以在地址栏左边的网站设置里打开", "error");
        return;
      }
      voice = "recording";
      seconds = 0;
      timer = window.setInterval(() => {
        seconds += 1;
        if (seconds >= MAX_SECONDS) void toggleVoice();
        sync();
      }, 1000);
    } else if (voice === "recording" && recorder) {
      window.clearInterval(timer);
      voice = "transcribing";
      sync();
      try {
        const wav = await recorder.stop();
        const { text } = await api.asr(wav);
        if (text) {
          textarea.value = textarea.value ? `${textarea.value.trimEnd()} ${text}` : text;
          voiceDraft = true;
          autosize();
          textarea.focus();
        } else {
          toast("没听清，再说一次试试", "info");
        }
      } catch (err) {
        toast(err instanceof ApiError ? err.message : "识别失败，再试一次", "error");
      } finally {
        recorder = null;
        voice = "idle";
      }
    }
    sync();
  }

  textarea.addEventListener("input", () => {
    autosize();
    if (!textarea.value.trim()) voiceDraft = false;
    sync();
  });
  textarea.addEventListener("keydown", (e) => {
    // 输入法选词时的回车不能当发送
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing && e.keyCode !== 229) {
      e.preventDefault();
      void submit();
    }
  });
  sendBtn.addEventListener("click", () => void submit());
  micBtn.addEventListener("click", () => void toggleVoice());

  function sync() {
    const cur = state.current;
    const disabled = busy();
    textarea.disabled = !cur?.live;
    sendBtn.disabled = disabled || !textarea.value.trim() || voice !== "idle";
    micBtn.disabled = !cur?.live || voice === "transcribing";
    micBtn.classList.toggle("recording", voice === "recording");
    micBtn.title = voice === "recording" ? "再点一下结束录音" : "语音输入";
    mount(micBtn, voice === "transcribing" ? icon(LoaderCircle, 16, "spin") : voice === "recording" ? icon(Square, 14) : icon(Mic, 16));
    if (!cur) hint.textContent = "先在左边新建一个对话";
    else if (!cur.live) hint.textContent = "这是历史会话，只能查看；新建对话才能继续";
    else if (voice === "recording") mount(hint, level, `正在听 ${seconds}s · 再点一下结束（最长 ${MAX_SECONDS}s）`);
    else if (voice === "transcribing") hint.textContent = "正在把语音转成文字…";
    else if (cur.busy) hint.textContent = "上一轮还在进行，稍等一下";
    else hint.textContent = "Enter 发送 · Shift+Enter 换行 · 语音转成文字后可以先改再发";
  }

  const el = h("div", { class: "composer" },
    h("div", { class: "composer-box" }, textarea, h("div", { class: "composer-actions" }, micBtn, sendBtn)),
    hint);
  sync();
  return { el, sync };
}
