"""技能选择 A/B：同一任务集分别跑"JEV 两级选择"和"主模型自选"，输出对照表。

  python -m eval.run_selection                         # 两臂都跑
  python -m eval.run_selection --arms jev --no-cache   # 只跑 JEV 臂，不用缓存（测真实延迟）

结果写到 var/eval/<时间>/：results.json（逐条）+ report.md（汇总表）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from agent.config import ROOT, Config
from agent.context import render_messages
from agent.decision import DecisionClient
from agent.kernel import Agent
from agent.router import ModelRouter
from agent.skills import SkillSelector

from .taskset import aggregate, load_taskset, score_task

METRICS = [
    ("exact", "完全正确率", "↑"), ("miss_rate", "漏选率", "↓"), ("wrong_rate", "误选率", "↓"),
    ("forced_rate", "硬凑率（none 类）", "↓"), ("confusions", "近义混淆次数", "↓"),
    ("tier_agree", "路由一致率", "↑"), ("avg_latency_s", "平均耗时(s)", "↓"),
    ("input_tokens", "选择阶段输入 token", "↓"), ("fallbacks", "降级次数", "↓"),
]


def run_arm(arm: str, tasks: list[dict], agent: Agent, decision: DecisionClient | None) -> list[dict]:
    use = decision if arm == "jev" else None
    selector = SkillSelector(agent.selector.skills, agent.th, use, agent.local)
    router = ModelRouter(agent.cfg, use)
    rows = []
    for t in tasks:
        recent = render_messages(t.get("context") or [], 1200)
        t0 = time.monotonic()
        sel = selector.select(t["input"], recent, mode=arm)
        tier = router._decide(t["input"], sel.skills, None)[0]
        exp = t["expect"]
        row = {
            "id": t["id"], "category": t["category"], "input": t["input"],
            "expected": exp["skills"], "selected": sel.names, "fallback": sel.fallback, "reason": sel.reason,
            "score": score_task(exp["skills"], sel.names, exp.get("confusable")),
            "tier": tier, "tier_ok": (tier == exp["tier"]) if exp.get("tier") else None,
            "latency_s": round(time.monotonic() - t0, 3), "usage": sel.usage, "detail": sel.detail,
        }
        mark = "✓" if row["score"]["exact"] else "✗"
        print(f"  {mark} {t['id']} 期望 {exp['skills'] or '无'} → {sel.names or '无'}"
              f"{'（降级）' if sel.fallback else ''}  路由 {tier}  {row['latency_s']}s", flush=True)
        rows.append(row)
    return rows


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", default=str(ROOT / "eval" / "tasks" / "skill-selection-v1.json"))
    p.add_argument("--arms", default="jev,baseline")
    p.add_argument("--no-cache", action="store_true")
    args = p.parse_args(argv)
    cfg = Config.load()
    cfg.memory_extract = False
    agent = Agent(cfg, use_jev=False)
    data = load_taskset(Path(args.tasks), {s.name for s in agent.selector.skills})
    decision = DecisionClient(cfg.jev_url, cfg.jev_model, cfg.jev_key,
                              cache_path=None if args.no_cache else cfg.data_dir / "cache" / "jev.sqlite",
                              mode="off" if args.no_cache else "live", use_proxy=cfg.jev_use_proxy)
    out_dir = cfg.data_dir / "eval" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {"taskset": data["name"], "arms": {}}
    all_rows = {}
    for arm in args.arms.split(","):
        print(f"== {arm}")
        rows = run_arm(arm, data["tasks"], agent, decision)
        all_rows[arm] = rows
        m = aggregate(rows)
        m["avg_latency_s"] = round(sum(r["latency_s"] for r in rows) / len(rows), 3)
        m["input_tokens"] = sum(int(r["usage"].get("input_tokens") or r["usage"].get("prompt_tokens") or 0)
                                for r in rows)
        m["fallbacks"] = sum(r["fallback"] for r in rows)
        report["arms"][arm] = m
    (out_dir / "results.json").write_text(
        json.dumps({"report": report, "rows": all_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    arms = list(report["arms"])
    lines = [f"# 技能选择 A/B：{data['name']}（{len(data['tasks'])} 条）", "",
             "| 指标 | " + " | ".join(arms) + " | 方向 |", "|---|" + "---|" * len(arms) + "---|"]
    for key, label, better in METRICS:
        lines.append(f"| {label} | " + " | ".join(str(report["arms"][a].get(key)) for a in arms) + f" | {better} |")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines))
    print(f"\n结果：{out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
