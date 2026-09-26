"""跑测试，只回报结论和失败项（不把整屏输出塞进上下文）。会执行工作区代码，走门控。

用法：test_report.py [测试路径或 pytest 参数…]
有 pytest 用 pytest（兼容 unittest 写的测试）；pytest 收集失败（常见于目录结构让它误判包路径）时退回 unittest 再试。
"""
import importlib.util
import re
import subprocess
import sys

extra = sys.argv[1:]
PYTEST = [sys.executable, "-m", "pytest", "-q", "--tb=line", "-p", "no:cacheprovider", *extra]
UNITTEST = [sys.executable, "-m", "unittest", "discover", "-v"]


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=55)
    except subprocess.TimeoutExpired:
        print("测试超时（55s）")
        sys.exit(1)


note = ""
if importlib.util.find_spec("pytest"):
    r = run(PYTEST)
    # 2 = 收集出错 / 4 = 用法错误 / 5 = 没收集到测试
    if r.returncode in (2, 4, 5) and not extra:
        u = run(UNITTEST)
        if "Ran " in u.stdout + u.stderr:
            note = f"（pytest 收集失败，退出码 {r.returncode}，已改用 unittest）"
            r = u
else:
    r = run(UNITTEST)

lines = (r.stdout + "\n" + r.stderr).strip().splitlines()
summary = next((l for l in reversed(lines)
                if re.search(r"\d+ (passed|failed)|Ran \d+ test|no tests ran|FAILED \(|^OK", l.strip())), "")
print(f"结论：{'全部通过' if r.returncode == 0 else '有失败'}（退出码 {r.returncode}）{note}")
if summary:
    print("统计：" + summary.strip(" =").strip())
if r.returncode != 0:
    fails = [l for l in lines if re.match(r"(FAILED|ERROR)\b|(FAIL|ERROR): ", l.strip())]
    detail = [l for l in lines if re.search(r"AssertionError|Error:|assert ", l)]
    print("失败项：")
    for l in (fails or lines[-25:])[:25]:
        print("  " + l.strip()[:240])
    if detail and fails:
        print("断言 / 异常：")
        for l in list(dict.fromkeys(detail))[:12]:
            print("  " + l.strip()[:240])
