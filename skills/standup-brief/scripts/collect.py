"""站会素材一次收齐：最近提交、未提交改动、最近一份纪要里的待办和未决事项。只读。

用法：collect.py [天数，默认 1]
工作目录是工作区根目录；纪要库路径从环境变量 VAULT 读。Linear 需要网络和 Key，脚本不碰，另用 linear_list_issues。
"""
import os
import re
import subprocess
import sys
from pathlib import Path

days = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 1


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() if r.returncode == 0 else f"（git 出错：{r.stderr.strip()[:120]}）"


print(f"## 最近 {days} 天的提交")
print(git("log", f"--since={days} days ago", "--pretty=format:%h %ad %s", "--date=format:%m-%d %H:%M") or "（没有提交）")
print("\n## 未提交的改动")
print(git("status", "--short") or "（工作区干净）")
print("\n## 当前分支")
print(git("branch", "--show-current") or "（游离 HEAD）")

vault = Path(os.environ.get("VAULT", ""))
notes = sorted((p for p in vault.rglob("*.md") if "纪要" in p.as_posix() or "会议" in p.name),
               key=lambda p: p.stat().st_mtime, reverse=True) if vault.is_dir() else []
print("\n## 最近一份纪要")
if not notes:
    print("（没找到纪要）")
else:
    note = notes[0]
    text = note.read_text(encoding="utf-8", errors="replace")
    print(note.relative_to(vault).as_posix())
    todo = [l.strip() for l in text.splitlines() if re.match(r"\s*[-*]\s*\[ \]", l)]
    pending = [l.strip() for l in text.splitlines() if re.search(r"没定|待定|待讨论|阻塞|blocked", l, re.I)]
    print("未完成待办：" + ("\n" + "\n".join(todo[:15]) if todo else "无"))
    print("未决 / 阻塞：" + ("\n" + "\n".join(pending[:10]) if pending else "无"))
