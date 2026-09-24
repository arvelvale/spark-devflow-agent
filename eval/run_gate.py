"""工具门控标定：用 eval/gate_cases.json 跑一遍当前门控问题，看合法/越界能不能分开。

  python -m eval.run_gate

改 agent/gate.py 里 gate_questions() 的措辞或 config.py 的门控阈值后都要重跑。
"""
from __future__ import annotations

import json
import sys

from agent.config import ROOT, Config, Thresholds
from agent.decision import DecisionClient
from agent.gate import ToolGate
from agent.tools import build_registry


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    cfg = Config.load()
    data = json.loads((ROOT / "eval" / "gate_cases.json").read_text(encoding="utf-8"))
    dc = DecisionClient(cfg.jev_url, cfg.jev_model, cfg.jev_key, mode="off", use_proxy=cfg.jev_use_proxy)
    th = Thresholds()
    gate = ToolGate(th, dc, confirm=lambda req: False)
    reg = build_registry()
    hits = 0
    for case in data["cases"]:
        r = gate.check(reg.get(case["tool"]), case["arguments"], allowed=True, goal=data["request"],
                       request=data["request"], plan=data["plan"])
        got = "allow" if r.decision == "allow" else "confirm"
        ok = got == case["expect"]
        hits += ok
        print(f"{'✓' if ok else '✗'} 期望 {case['expect']:7} 实际 {got:7} 合理={r.appropriate:.2f} 越界={r.collateral:.2f}"
              f"  {case['tool']} {json.dumps(case['arguments'], ensure_ascii=False)[:48]}")
    print(f"\n{hits}/{len(data['cases'])} 符合期望（阈值：合理 ≥ {th.gate_write}，越界 < {th.gate_collateral}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
