---
name: branch-hygiene
description: >-
  分支卫生检查：检查当前分支命名规范、未提交改动、与 main 的同步状态，给出清理建议。只读，不修改任何内容。
version: 0.1.1
argument-hint: ""
model: local
allowed-tools: []
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
1. `git_status` 拿当前分支名和未提交的改动（只读工具，不需要 `run_command`；`run_command` 的白名单里没有 git 命令）。
2. 检查分支名是否符合规范（如 `agent/<issue-编号>` 或 `feat/` / `fix/` 前缀），不符合的标黄。
3. `git_diff` 的 `target` 填 `main..HEAD`，看本分支领先 main 的改动；`git_log` 看最近提交。
4. 落后 main 多少：现有工具算不出精确提交数，如实写"未统计"，不要估。
5. 综合以上信息给出卫生评分和建议。

## 输出契约
给出分支名、命名是否合规、未提交改动数、领先 main 的改动概况、是否建议 rebase/merge，以及是否需要清理。

## 不要做
- 不自动执行 git 操作（只读检查）
- 不修改任何文件或提交
