---
name: implement-change
description: >-
  实现 / 开发 / 修 bug / 改代码 / implement：按 issue 或计划在工作区修改代码、补测试并跑通，在独立分支上提交。
version: 0.1.0
argument-hint: "<issue 编号、计划文件或要改的内容>"
model: auto
allowed-tools:
  - write_file
  - edit_file
  - run_command
  - git_branch
  - git_commit
triggers:
  - 把金额精度的 bug 修了
  - 按 docs/plans 里的计划把 CSV 导出实现一下
  - 给 summary 命令补上测试
not-for:
  - 先写个方案别动代码 → plan-writer
  - 看看这次改动有没有违反约定 → review-gate
tags: [dev-flow, code]
---
# 实现改动

## 什么时候用
需要真正修改代码时。改之前如果有计划文档（`docs/plans/`），先读计划并按切片做。

## 步骤
1. 读 `AGENTS.md` 的代码约定；读 issue 或计划；用 `update_plan` 列出切片待办。
2. 先按 `AGENTS.md` 里的测试命令跑一次（`run_command`，一般是 `python -m unittest`），记下基线。
3. 在 `agent/<issue 编号或短名>` 分支上工作（`git_branch`）。已经在非 main 分支上就不用新建。
4. 小步修改：优先 `edit_file` 局部替换；新文件用 `write_file`。
5. 修 bug 先写能复现问题的测试，再改代码。
6. 每完成一个切片：跑测试 → 通过后 `git_commit`（中文提交说明，一句话说清做了什么）→ 在 `update_plan` 里勾掉。
7. 测试失败：读报错、定位、修复；同一处失败三次仍修不好就停下，如实报告。
8. 每次 `git_commit` 之前，先跑 `run_command` 执行 `git diff --cached --stat`，确认只有预期文件被改动；如果出现意外删除或无关文件修改，停下报告。

## 输出契约
回复包含：分支名、提交列表（短哈希 + 说明）、测试结果（通过数/失败数）、没完成的事。

## 不要做
- 不在 main 分支上直接提交
- 不改与任务无关的文件，不顺手重构
- 不删除或跳过已有测试来让测试通过
- 不跳过提交前的 git diff 检查：每次 commit 前必须确认只有预期文件改动
