import type { MemoryItem, ModelsView, ProviderInput, SessionDetail, SessionSummary, Slot, SlotRef, Status } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown, raw?: Blob): Promise<T> {
  const init: RequestInit = { method, credentials: "same-origin", headers: {} };
  if (raw) {
    init.body = raw;
    (init.headers as Record<string, string>)["Content-Type"] = raw.type || "application/octet-stream";
  } else if (body !== undefined) {
    init.body = JSON.stringify(body);
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  let resp: Response;
  try {
    resp = await fetch(path, init);
  } catch {
    throw new ApiError(0, "连不上面板后端，看看节点上的服务还在不在");
  }
  const text = await resp.text();
  const data = text ? safeJson(text) : null;
  if (!resp.ok) {
    const msg = (data && typeof data === "object" && "error" in data ? String(data.error) : "") || `请求失败（${resp.status}）`;
    if (resp.status === 401 && path !== "/api/login") window.dispatchEvent(new Event("dgx:unauthorized"));
    throw new ApiError(resp.status, msg);
  }
  return data as T;
}

function safeJson(text: string): any {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export const api = {
  login: (token: string) => request<{ ok: boolean }>("POST", "/api/login", { token }),
  logout: () => request<{ ok: boolean }>("POST", "/api/logout", {}),
  status: () => request<Status>("GET", "/api/status"),
  sessions: () => request<SessionSummary[]>("GET", "/api/sessions"),
  createSession: (useJev: boolean, tier: string) =>
    request<{ id: string }>("POST", "/api/sessions", { use_jev: useJev, tier }),
  session: (id: string) => request<SessionDetail>("GET", `/api/sessions/${encodeURIComponent(id)}`),
  setTier: (id: string, tier: string) =>
    request<{ tier: string }>("PATCH", `/api/sessions/${encodeURIComponent(id)}`, { tier }),
  turn: (id: string, text: string, source: "text" | "voice") =>
    request<{ ok: boolean }>("POST", `/api/sessions/${encodeURIComponent(id)}/turn`, { text, source }),
  confirm: (id: string, confirmId: string, approve: boolean) =>
    request<{ ok: boolean }>("POST", `/api/sessions/${encodeURIComponent(id)}/confirm`, { id: confirmId, approve }),
  memory: (status: "active" | "pending") => request<MemoryItem[]>("GET", `/api/memory?status=${status}`),
  approveMemory: (id: string) => request<{ ok: boolean }>("POST", `/api/memory/${encodeURIComponent(id)}/approve`, {}),
  forgetMemory: (id: string) => request<{ ok: boolean }>("DELETE", `/api/memory/${encodeURIComponent(id)}`),
  models: () => request<ModelsView>("GET", "/api/models"),
  setSlots: (slots: Partial<Record<Slot, SlotRef>>) => request<ModelsView>("PUT", "/api/models/slots", slots),
  saveProvider: (id: string, body: ProviderInput) =>
    request<ModelsView>("PUT", `/api/models/providers/${encodeURIComponent(id)}`, body),
  deleteProvider: (id: string) => request<ModelsView>("DELETE", `/api/models/providers/${encodeURIComponent(id)}`),
  discoverModels: (id: string) =>
    request<{ models: string[] }>("POST", `/api/models/providers/${encodeURIComponent(id)}/discover`, {}),
  testModel: (id: string, model: string) =>
    request<{ ok: boolean; latency_ms?: number; reply?: string; error?: string }>(
      "POST", `/api/models/providers/${encodeURIComponent(id)}/test`, { model }),
  asr: (wav: Blob) => request<{ text: string }>("POST", "/api/asr?format=wav", undefined, wav),
  streamUrl: (id: string) => `/api/sessions/${encodeURIComponent(id)}/stream`,
};
