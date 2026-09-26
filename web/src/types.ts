// 与 docs/接口/03-决策轨迹格式.md 对应。读取方要忽略不认识的事件类型和字段（向前兼容）。

export type EventType =
  | "turn.start" | "skill.select" | "route.model" | "route.escalate" | "memory.recall"
  | "llm.call" | "tool.gate" | "tool.call" | "context.compress" | "memory.write"
  | "turn.end" | "error" | "subagent.start" | "subagent.end" | "guard.drift";

export interface Usage { input_tokens: number; output_tokens: number }

export interface TraceEvent {
  v: number;
  ts: string;
  session: string;
  turn: number;
  seq: number;
  type: EventType | string;
  data: Record<string, any>;
  latency_ms?: number;
  provider?: string;
  model?: string;
  usage?: Usage;
  fallback?: boolean;
}

export interface Message { turn: number; role: "user" | "assistant"; content: string }

export interface Working {
  goal: string;
  constraints: string[];
  todo: { item: string; done: boolean }[];
  evidence: string[];
}

export interface ConfirmItem {
  id: string;
  turn: number;
  tool: string;
  permission: "write_local" | "external" | string;
  arguments: Record<string, unknown>;
  reason: string;
  in_scope: number | null;
  collateral: number | null;
  created: number;
  resolved?: { approve: boolean; timeout: boolean };
}

export interface TurnDone {
  turn: number;
  reply?: string;
  tier?: string;
  steps?: number;
  stopped?: string;
  tokens?: Record<string, Usage>;
  latency?: number;
  skills?: string[];
  error?: string;
}

export interface SessionDetail {
  id: string;
  live: boolean;
  busy: boolean;
  use_jev: boolean | null;
  tier: string | null;
  events: TraceEvent[];
  messages: Message[];
  working: Working | null;
  pending: ConfirmItem[];
}

export interface SessionSummary { id: string; updated: number; turns: number; title: string; live: boolean }

export interface Service { ok: boolean; model: string; private?: boolean }

export interface Status {
  services: Record<"local" | "backup" | "cloud" | "jev" | "linear", Service>;
  workspace: string;
  workspace_ready: boolean;
  skills: { name: string; description: string; model: string; writes: string[] }[];
  skill_errors: string[];
}

export interface MemoryItem {
  id: string;
  layer: string;
  kind: string;
  content: string;
  privacy: "shareable" | "local" | string;
  status: string;
  created: number;
  used: number;
}

/** 前端把一轮的所有东西归在一起 */
export interface Turn {
  n: number;
  input: string;
  source: string;
  events: TraceEvent[];
  reply?: string;
  done?: TurnDone;
}

// ---- 模型设置（/api/models）：Key 原文永远不下发 ----
export type Slot = "local" | "backup" | "cloud";
export interface SlotRef { provider: string; model: string }
export interface ProviderView {
  id: string;
  name: string;
  base_url: string;
  private: boolean;
  use_proxy: boolean;
  has_key: boolean;
  key_source: "panel" | "env" | null;
  key_env: string;
  models: { name: string; max_tokens: number }[];
}
export interface Preset { id: string; name: string; base_url: string; use_proxy?: boolean; private?: boolean }
export interface ModelsView {
  saved: boolean;
  providers: ProviderView[];
  slots: Partial<Record<Slot, SlotRef>>;
  presets: Preset[];
}
export interface ProviderInput {
  name: string;
  base_url: string;
  api_key?: string;
  private: boolean;
  use_proxy: boolean;
  models: { name: string; max_tokens?: number }[];
}
