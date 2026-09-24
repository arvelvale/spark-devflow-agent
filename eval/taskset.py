"""任务集加载、校验、打分。格式契约见 docs/接口/02-任务集格式.md。"""
from __future__ import annotations

import json
from pathlib import Path

CATEGORIES = {"single", "none", "multi"}
TIERS = {"local", "cloud"}


def validate_taskset(data: dict, known_skills: set[str] | None = None) -> list[str]:
    problems = []
    if data.get("version") != 1:
        problems.append("version 必须为 1")
    if not data.get("name"):
        problems.append("缺少 name")
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return problems + ["tasks 必须是非空列表"]
    seen = set()
    for t in tasks:
        tid = t.get("id", "?")
        if tid in seen:
            problems.append(f"{tid}: id 重复")
        seen.add(tid)
        cat = t.get("category")
        if cat not in CATEGORIES:
            problems.append(f"{tid}: category 必须是 {sorted(CATEGORIES)}")
        if not str(t.get("input", "")).strip():
            problems.append(f"{tid}: input 为空")
        exp = t.get("expect") or {}
        skills = exp.get("skills")
        if not isinstance(skills, list):
            problems.append(f"{tid}: expect.skills 必须是列表")
            continue
        if cat == "none" and skills:
            problems.append(f"{tid}: none 类的 expect.skills 必须为空")
        if cat == "single" and len(skills) != 1:
            problems.append(f"{tid}: single 类恰好 1 个技能")
        if cat == "multi" and len(skills) < 2:
            problems.append(f"{tid}: multi 类至少 2 个技能")
        if exp.get("tier") is not None and exp["tier"] not in TIERS:
            problems.append(f"{tid}: expect.tier 必须是 local 或 cloud")
        for ctx in t.get("context") or []:
            if ctx.get("role") not in {"user", "assistant"} or "content" not in ctx:
                problems.append(f"{tid}: context 每项需要 role(user/assistant) 和 content")
        if known_skills is not None:
            unknown = [s for s in skills + list(exp.get("confusable") or []) if s not in known_skills]
            if unknown:
                problems.append(f"{tid}: 未知技能 {unknown}")
    return problems


def load_taskset(path: Path, known_skills: set[str] | None = None) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = validate_taskset(data, known_skills)
    if problems:
        raise ValueError(f"{path} 校验失败：\n" + "\n".join(problems))
    return data


def score_task(expected: list[str], selected: list[str], confusable: list[str] | None = None) -> dict:
    e, s = set(expected), set(selected)
    return {
        "exact": e == s,
        "miss": bool(e) and not e <= s,       # 期望的技能没选全
        "wrong": bool(s - e),                 # 选了不该选的
        "forced": not e and bool(s),          # 不该用技能却硬凑
        "confused": sorted(s & set(confusable or [])),
    }


def aggregate(rows: list[dict]) -> dict:
    """rows: [{"category", "score": score_task(...), "tier_ok": bool | None, ...}]"""
    with_expect = [r for r in rows if r["category"] != "none"]
    nones = [r for r in rows if r["category"] == "none"]
    tiered = [r for r in rows if r.get("tier_ok") is not None]

    def rate(items, key):
        return round(sum(r["score"][key] for r in items) / len(items), 3) if items else None

    return {
        "tasks": len(rows),
        "exact": rate(rows, "exact"),
        "miss_rate": rate(with_expect, "miss"),
        "wrong_rate": rate(rows, "wrong"),
        "forced_rate": rate(nones, "forced"),
        "confusions": sum(len(r["score"]["confused"]) for r in rows),
        "tier_agree": round(sum(r["tier_ok"] for r in tiered) / len(tiered), 3) if tiered else None,
        "by_category": {c: rate([r for r in rows if r["category"] == c], "exact")
                        for c in ("single", "none", "multi")},
    }
