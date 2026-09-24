"""长期记忆（架构第 5 节，第一阶段最小实现）。

分层：episodic（发生过的事，每轮自动写一条）/ semantic（提炼出的事实、约定、决定）/ profile（用户偏好）。
工作记忆在 context.WorkingState，不进这里。

取：本地关键词召回（中文二元组 + 英文词 + 实体精确匹配，不上向量库）→ JEV 逐条判相关度 → 代码按阈值分三档。
存：episodic 直接写；semantic/profile 候选由本地模型抽取 → JEV 判"值不值得长期记住" → 生效 / 待确认 / 丢弃。

隐私：privacy=local 的记忆永远不进 JEV 的 state，路由到云端的轮次也不放进上下文。
（深度标签是软约束，真正的边界是这里和 kernel 里的过滤代码。）
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from .decision import DecisionClient, DecisionUnavailable, clip, noul
from .llm import extract_json

if TYPE_CHECKING:
    from .config import Thresholds
    from .trace import Trace

LAYERS = ("episodic", "semantic", "profile")
KINDS = ("event", "fact", "convention", "decision", "preference")

WORD = re.compile(r"[A-Za-z][A-Za-z0-9_.\-/]{1,}")
CJK_RUN = re.compile(r"[一-鿿]+")
ENTITY = re.compile(r"\b[A-Z]{2,10}-\d+\b|(?:[\w.-]+/)+[\w.-]+|\b[\w-]+\.(?:py|md|json|toml|txt|csv)\b")


def tokens(text: str) -> set[str]:
    """检索用的词元：英文词（小写）+ 中文二元组 + 单个汉字（兜底两字以下的词）。"""
    text = text or ""
    out = {w.lower() for w in WORD.findall(text)}
    for run in CJK_RUN.findall(text):
        if len(run) == 1:
            out.add(run)
        out.update(run[i:i + 2] for i in range(len(run) - 1))
    return out


def entities(text: str) -> set[str]:
    return set(ENTITY.findall(text or ""))


@dataclass
class Memory:
    id: str
    layer: str
    kind: str
    content: str
    entities: list[str] = field(default_factory=list)
    source: str = ""
    session: str = ""
    created_at: float = field(default_factory=time.time)
    last_used_at: float = 0.0
    use_count: int = 0
    privacy: str = "shareable"   # shareable / local
    status: str = "active"       # active / pending / archived

    def line(self) -> str:
        day = time.strftime("%m-%d", time.localtime(self.created_at))
        return f"[{self.id}·{self.kind}·{day}] {self.content}"


class MemoryStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._db.execute("""CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY, layer TEXT, kind TEXT, content TEXT, entities TEXT, source TEXT,
            session TEXT, created_at REAL, last_used_at REAL, use_count INTEGER, privacy TEXT, status TEXT)""")
        self._db.commit()

    @staticmethod
    def _row(r: sqlite3.Row) -> Memory:
        d = dict(r)
        d["entities"] = json.loads(d["entities"] or "[]")
        return Memory(**d)

    def add(self, layer: str, kind: str, content: str, *, source: str = "", session: str = "",
            privacy: str = "shareable", status: str = "active") -> Memory:
        assert layer in LAYERS and kind in KINDS, (layer, kind)
        m = Memory(id=uuid.uuid4().hex[:8], layer=layer, kind=kind, content=content.strip(),
                   entities=sorted(entities(content)), source=source, session=session,
                   privacy=privacy if privacy in ("shareable", "local") else "local", status=status)
        with self._lock:
            self._db.execute("INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                m.id, m.layer, m.kind, m.content, json.dumps(m.entities, ensure_ascii=False), m.source,
                m.session, m.created_at, m.last_used_at, m.use_count, m.privacy, m.status))
            self._db.commit()
        return m

    def get(self, mid: str) -> Memory | None:
        r = self._db.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()
        return self._row(r) if r else None

    def list(self, status: str | None = "active", layer: str | None = None) -> list[Memory]:
        sql, args = "SELECT * FROM memories WHERE 1=1", []
        if status:
            sql += " AND status=?"
            args.append(status)
        if layer:
            sql += " AND layer=?"
            args.append(layer)
        return [self._row(r) for r in self._db.execute(sql + " ORDER BY created_at DESC", args)]

    def set_status(self, mid: str, status: str) -> bool:
        with self._lock:
            cur = self._db.execute("UPDATE memories SET status=? WHERE id=?", (status, mid))
            self._db.commit()
        return cur.rowcount > 0

    def delete(self, mid: str) -> bool:
        with self._lock:
            cur = self._db.execute("DELETE FROM memories WHERE id=?", (mid,))
            self._db.commit()
        return cur.rowcount > 0

    def mark_used(self, ids: list[str]) -> None:
        if not ids:
            return
        with self._lock:
            self._db.executemany("UPDATE memories SET last_used_at=?, use_count=use_count+1 WHERE id=?",
                                 [(time.time(), i) for i in ids])
            self._db.commit()

    def recall(self, query: str, k: int = 8) -> list[tuple[Memory, float]]:
        """关键词召回：BM25 风格的词元重叠（按稀有度加权）+ 实体精确命中 + 轻微新近度加成。"""
        pool = self.list("active")
        if not pool:
            return []
        q_tokens, q_ents = tokens(query), entities(query)
        docs = [(m, tokens(m.content)) for m in pool]
        n = len(docs)
        df: dict[str, int] = {}
        for _, toks in docs:
            for t in toks:
                df[t] = df.get(t, 0) + 1
        now = time.time()
        scored = []
        for m, toks in docs:
            overlap = q_tokens & toks
            s = sum(math.log(1 + n / df[t]) for t in overlap)
            s += 2.0 * len(q_ents & set(m.entities))
            if s <= 0:
                continue
            s /= math.sqrt(len(toks) + 1) / 3  # 长记忆不因词多占便宜
            s += 0.2 * math.exp(-(now - m.created_at) / (14 * 86400))
            scored.append((m, round(s, 4)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def near_duplicate(self, content: str, jaccard: float = 0.8, coverage: float = 0.65) -> Memory | None:
        """同义改写的同一事实也算重复。2026-09-24 实测：同一事实换个说法 Jaccard 只有 0.45–0.59，
        但较短一条被覆盖的比例 0.72–1.00；不同事实的覆盖率 ≤ 0.38。"""
        toks = tokens(content)
        if not toks:
            return None
        for m in self.list("active") + self.list("pending"):
            if m.layer == "episodic":
                continue
            other = tokens(m.content)
            if not other:
                continue
            common = len(toks & other)
            if common / len(toks | other) >= jaccard:
                return m
            if min(len(toks), len(other)) >= 4 and common / min(len(toks), len(other)) >= coverage:
                return m
        return None


@dataclass
class MemorySelection:
    full: list[Memory] = field(default_factory=list)
    brief: list[Memory] = field(default_factory=list)
    detail: dict = field(default_factory=dict)
    fallback: bool = False

    def render(self) -> str:
        lines = [m.line() for m in self.full] + [f"{m.line()[:80]}（仅供参考）" for m in self.brief]
        return "\n".join(lines)


EXTRACT_PROMPT = """从下面这轮对话里找出值得长期记住的信息（最多 3 条），只要以后换个会话还用得上的：
- fact：关于项目的事实（如"金额按分存整数"）
- convention：团队/仓库约定（如"日志写在 docs/progress/日期.md"）
- decision：做出的决定及原因
- preference：用户的个人偏好（如"回复要先给结论"）
不要记：一次性的中间结果、已经写进代码或文档的细节、密钥和账号。
privacy 字段：涉及个人信息、情绪、健康、账号的填 "local"，其余填 "shareable"。
没有值得记的就输出 []。只输出 JSON 数组：
[{{"content": "...", "kind": "fact|convention|decision|preference", "privacy": "shareable|local"}}]

对话：
{text}"""


class MemoryManager:
    def __init__(self, store: MemoryStore, thresholds: "Thresholds", decision: DecisionClient | None,
                 extract: Callable[[str], str] | None = None, trace: "Trace | None" = None, session: str = ""):
        self.store = store
        self.th = thresholds
        self.decision = decision
        self.extract = extract
        self.trace = trace
        self.session = session

    # ---------- 取 ----------
    def select(self, request: str, goal: str, tier: str) -> MemorySelection:
        candidates = self.store.recall(f"{goal}\n{request}", self.th.memory_recall_k)
        sel = MemorySelection()
        excluded = []
        judged: list[tuple[Memory, float]] = []
        private: list[Memory] = []
        for m, kw in candidates:
            if m.privacy == "local":
                if tier == "cloud":
                    excluded.append(m.id)  # 云端轮次：隐私记忆不进上下文
                else:
                    private.append(m)      # 本地轮次：不送 JEV，只按关键词放进摘要位
            else:
                judged.append((m, kw))
        relevance: dict[str, float] = {}
        if judged and self.decision and self.decision.available:
            state = {"request": clip(request, 800), "goal": clip(goal or request, 300),
                     "memories": {f"m_{m.id}": clip(m.content, 400) for m, _ in judged}}
            qs = {f"rel_{m.id}": noul(
                f"记忆 `memories.m_{m.id}` 对完成 `request` 是否有直接帮助？只是话题相近但用不上的，回答否。")
                for m, _ in judged}
            try:
                d = self.decision.ask(state, qs)
                relevance = {m.id: d.noul(f"rel_{m.id}") for m, _ in judged}
            except DecisionUnavailable:
                sel.fallback = True
        elif judged:
            sel.fallback = True
        if sel.fallback:
            # 降级：关键词排序前 3 条放摘要位，交主模型自行判断
            sel.brief = [m for m, _ in judged[:3]]
        else:
            for m, _ in judged:
                v = relevance[m.id]
                if v >= self.th.memory_full:
                    sel.full.append(m)
                elif v >= self.th.memory_brief:
                    sel.brief.append(m)
        sel.brief += private[:2]
        self.store.mark_used([m.id for m in sel.full + sel.brief])
        sel.detail = {
            "candidates": [{"id": m.id, "kw": kw} for m, kw in candidates],
            "full": [m.id for m in sel.full],
            "brief": [m.id for m in sel.brief],
            "dropped": [{"id": i, "relevant": round(v, 3)} for i, v in relevance.items()
                        if i not in {m.id for m in sel.full + sel.brief}],
            "relevance": {i: round(v, 3) for i, v in relevance.items()},
            "excluded_private": excluded,
        }
        if self.trace:
            self.trace.emit("memory.recall", sel.detail, fallback=sel.fallback)
        return sel

    # ---------- 存 ----------
    def write_back(self, request: str, skills: list[str], tool_log: list[dict], reply: str,
                   transcript: str) -> list[dict]:
        items = []
        tools_used = "、".join(f"{t['tool']}{'' if t['ok'] else '(失败)'}" for t in tool_log[:12]) or "无"
        episode = (f"请求：{clip(request, 120)}｜技能：{'、'.join(skills) or '无'}｜工具：{tools_used}"
                   f"｜结果：{clip(reply, 160)}")
        m = self.store.add("episodic", "event", episode, source="turn", session=self.session)
        items.append({"id": m.id, "layer": "episodic", "kind": "event", "status": "active"})

        for cand in self._extract(transcript):
            dup = self.store.near_duplicate(cand["content"])
            if dup:
                self.store.mark_used([dup.id])
                items.append({"id": dup.id, "status": "duplicate"})
                continue
            worth, status = self._judge_worth(cand)
            if status == "discard":
                items.append({"content": clip(cand["content"], 60), "status": "discard", "worth": worth})
                continue
            layer = "profile" if cand["kind"] == "preference" else "semantic"
            m = self.store.add(layer, cand["kind"], cand["content"], source="extract",
                               session=self.session, privacy=cand["privacy"], status=status)
            items.append({"id": m.id, "layer": layer, "kind": m.kind, "status": status, "worth": worth})
        if self.trace:
            self.trace.emit("memory.write", {"items": items})
        return items

    def _extract(self, transcript: str) -> list[dict]:
        if not self.extract:
            return []
        try:
            data = extract_json(self.extract(EXTRACT_PROMPT.format(text=clip(transcript, 5000))))
        except Exception:
            return []
        out = []
        for c in data if isinstance(data, list) else []:
            if not isinstance(c, dict) or not str(c.get("content", "")).strip():
                continue
            kind = c.get("kind") if c.get("kind") in KINDS[1:] else "fact"
            out.append({"content": clip(str(c["content"]).strip(), 300), "kind": kind,
                        "privacy": "local" if c.get("privacy") == "local" else "shareable"})
        return out[:3]

    def _judge_worth(self, cand: dict) -> tuple[float | None, str]:
        """worth ≥ memory_keep → active；[memory_pending, memory_keep) → pending；更低 → discard。
        隐私候选和 JEV 不可用时一律进待确认区，由用户决定（不强行替用户记）。"""
        if cand["privacy"] == "local" or not (self.decision and self.decision.available):
            return None, "pending"
        try:
            d = self.decision.ask({"candidate": cand["content"], "kind": cand["kind"]}, {
                "worth": noul("`candidate` 是否值得长期记住：换一个会话、过一周以后，它仍然会影响怎么完成开发任务？"
                              "一次性的中间结果或显而易见的常识回答否。")})
            worth = d.noul("worth")
        except DecisionUnavailable:
            return None, "pending"
        if worth >= self.th.memory_keep:
            return round(worth, 3), "active"
        if worth >= self.th.memory_pending:
            return round(worth, 3), "pending"
        return round(worth, 3), "discard"
