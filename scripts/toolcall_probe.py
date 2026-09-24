"""节点上验证本地模型的 OpenAI 兼容工具调用：选对工具、参数正确、能用工具结果收尾。"""
import json, sys, time, urllib.request

BASE, MODEL = sys.argv[1], sys.argv[2]
EXTRA = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
TOOLS = [
    {"type": "function", "function": {"name": "git_log", "description": "查看仓库最近的提交记录（只读）",
     "parameters": {"type": "object", "properties": {"n": {"type": "integer", "description": "条数"}}, "required": ["n"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "读取仓库内的文件",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
]
FAKE = {"git_log": "a1b2c3 修复金额累加精度：改为按分存整数\nd4e5f6 新增 CSV 导出命令\n0719aa 初始化项目",
        "read_file": "# tinyledger\n一个命令行记账工具。命令：add / list / export"}
CASES = [("看一下最近 3 条提交都做了什么，用一句话总结", "git_log", {"n": 3}),
         ("README.md 里写了哪些命令？", "read_file", {"path": "README.md"})]

def chat(messages):
    body = {"model": MODEL, "messages": messages, "tools": TOOLS, "temperature": 0, "max_tokens": 1024, **EXTRA}
    req = urllib.request.Request(BASE + "/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time(); d = json.load(urllib.request.urlopen(req, timeout=300)); return d, time.time() - t

ok = 0
for prompt, want_tool, want_args in CASES:
    msgs = [{"role": "user", "content": prompt}]
    d, t1 = chat(msgs); m = d["choices"][0]["message"]; calls = m.get("tool_calls") or []
    got = [(c["function"]["name"], json.loads(c["function"]["arguments"] or "{}")) for c in calls]
    hit = bool(got) and got[0][0] == want_tool and all(got[0][1].get(k) == v for k, v in want_args.items())
    final, t2 = "", 0.0
    if calls:
        msgs += [m] + [{"role": "tool", "tool_call_id": c["id"], "content": FAKE[c["function"]["name"]]} for c in calls]
        d2, t2 = chat(msgs); final = (d2["choices"][0]["message"].get("content") or "").strip()
    ok += hit and bool(final)
    print(f"[{'OK' if hit and final else 'FAIL'}] {prompt}\n  调用={got} 第一轮 {t1:.1f}s usage={d.get('usage')}\n  收尾({t2:.1f}s)：{final[:160]!r}")
print(f"通过 {ok}/{len(CASES)}")
