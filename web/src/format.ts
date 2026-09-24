export function ms(v: number | undefined | null): string {
  if (v === undefined || v === null) return "—";
  if (v < 1000) return `${Math.round(v)} ms`;
  if (v < 60_000) return `${(v / 1000).toFixed(1)} s`;
  const m = Math.floor(v / 60_000);
  return `${m} 分 ${Math.round((v % 60_000) / 1000)} 秒`;
}

export function tokens(n: number | undefined | null): string {
  if (!n) return "0";
  if (n < 1000) return String(n);
  return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)}k`;
}

export function num(v: number | undefined | null, digits = 2): string {
  return v === undefined || v === null ? "—" : v.toFixed(digits);
}

export function when(epochSeconds: number): string {
  const d = new Date(epochSeconds * 1000);
  const now = new Date();
  const hm = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  if (d.toDateString() === now.toDateString()) return hm;
  return `${d.getMonth() + 1}月${d.getDate()}日 ${hm}`;
}

/** 技能在 JEV 里用下划线键名，展示时还原成 kebab */
export function skillName(key: string): string {
  return key === "none" ? "不用技能" : key.replace(/_/g, "-");
}

export const TIER_LABEL: Record<string, string> = { local: "本地", cloud: "云端" };

export const ENDPOINT_LABEL: Record<string, string> = {
  local: "本地 Nemotron",
  backup: "本地备用 Qwen",
  cloud: "云端 step-5",
  jev: "JEV",
};

export const PERMISSION_LABEL: Record<string, string> = {
  read: "只读",
  write_local: "本地写",
  external: "外部可见",
};

export const GATE_LABEL: Record<string, string> = { allow: "放行", confirm: "需确认", deny: "拦截" };

export const DIFFICULTY_LABEL: Record<string, string> = { simple: "简单", moderate: "中等", hard: "困难" };
