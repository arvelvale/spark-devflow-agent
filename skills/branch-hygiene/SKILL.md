---
name: branch-hygiene
description: >-
  分支卫生检查：检查当前分支命名规范、未提交改动、与 main 的同步状态，给出清理建议。只读，不修改任何内容。
version: 0.1.0
argument-hint: ""
model: local
allowed-tools:
  - run_command
triggers:
  - 检查一下分支卫生
  - 我的分支命名规范吗
  - 这个分支落后 main 多少
not-for:
  - 直接在分支上改代码 → implement-change
  - review 一下代码改动 → review-gate
  - 清理过期分支 → 手动执行 git 命令
internal: true
tags: [dev-flow, 只读]
---
# 分支卫生检查

## 什么时候用
定期检查或用户要求确认当前分支的健康状况。只读检查，不改文件、不提交。

## 步骤
1. `run_command` 执行 `git branch --show-current` 获取当前分支名。
2. 检查分支名是否符合规范（如 `agent/<issue-编号>` 或 `feat/` / `fix/` 前缀），不符合的标黄。
3. `run_command` 执行 `git status --short` 看是否有未提交改动；`git diff --cached --stat` 看已暂存的改动。
4. `run_command` 执行 `git rev-list --count main..HEAD` 和 `git rev-list --count HEAD..main` 计算与 main 的提交差距。
5. 综合以上信息给出卫生评分和建议。

## 输出契约
给出分支名、命名是否合规、未提交改动数、与 main 的提交差距、是否建议 rebase/merge，以及是否需要清理。

## 不要做
- 不自动执行 git 操作（只读检查）
- 不修改任何文件或提交
