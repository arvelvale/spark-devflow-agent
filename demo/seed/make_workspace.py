"""生成演示工作区：把 tinyledger 模板做成一个带历史提交的 git 仓库。

  python demo/seed/make_workspace.py            # 生成到 var/workspace/tinyledger
  python demo/seed/make_workspace.py --force    # 已存在就删掉重建（录视频前重置用）

历史提交（虚构作者，日期回填）：
  09-20 小林  初始化 tinyledger：add / list 命令
  09-22 阿泽  补 9/22 开发日志
  09-23 周周  约定新增：金额不得用 float 累加（周会决定）
故意保留的问题：store.py 里金额仍是 float 累加（周会纪要里的 bug），CSV 导出和月度汇总还没做。
"""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMPLATE = HERE / "tinyledger"
MONEY_RULE = "\n## 金额\n9. 金额计算不得用 float 累加，统一按\"分\"存整数，读取老数据时自动换算（2026-09-23 周会决定）。\n"

COMMITS = [
    ("小林", "xiaolin@example.com", "2026-09-20T15:10:00+08:00", "初始化 tinyledger：add / list 命令"),
    ("阿泽", "aze@example.com", "2026-09-22T21:40:00+08:00", "补 9/22 开发日志"),
    ("周周", "zhouzhou@example.com", "2026-09-23T18:05:00+08:00", "约定新增：金额不得用 float 累加（周会决定）"),
]


def git(cwd: Path, *args: str, env: dict | None = None) -> str:
    out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                         env={**os.environ, **(env or {})})
    if out.returncode != 0:
        sys.exit(f"git {' '.join(args)} 失败：{out.stderr.strip()}")
    return out.stdout.strip()


def commit(dest: Path, idx: int) -> str:
    name, email, when, msg = COMMITS[idx]
    env = {"GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_AUTHOR_DATE": when,
           "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email, "GIT_COMMITTER_DATE": when}
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", msg, env=env)
    return git(dest, "rev-parse", "--short", "HEAD")


def _rm_readonly(func, path, _):
    os.chmod(path, stat.S_IWRITE)  # Windows 上 .git 里有只读文件
    func(path)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dest", default=str(ROOT / "var" / "workspace" / "tinyledger"))
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    dest = Path(args.dest)
    if dest.exists():
        if not args.force:
            sys.exit(f"{dest} 已存在；要重建请加 --force")
        shutil.rmtree(dest, onerror=_rm_readonly)
    progress = TEMPLATE / "docs" / "progress" / "2026-09-22.md"
    shutil.copytree(TEMPLATE, dest, ignore=shutil.ignore_patterns("__pycache__", "2026-09-22.md"))
    (dest / ".gitignore").write_text("__pycache__/\nledger.json\n", encoding="utf-8")
    git(dest, "init", "-q", "-b", "main")
    h1 = commit(dest, 0)
    (dest / "docs" / "progress" / "2026-09-22.md").write_text(
        progress.read_text(encoding="utf-8").replace("{HASH_INIT}", h1), encoding="utf-8")
    commit(dest, 1)
    with (dest / "AGENTS.md").open("a", encoding="utf-8") as fh:
        fh.write(MONEY_RULE)
    commit(dest, 2)
    print(f"已生成 {dest}")
    print(git(dest, "log", "--oneline"))


if __name__ == "__main__":
    main()
