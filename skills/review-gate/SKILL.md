---
name: review-gate
description: >-
  审查 / review / 检查规范 / 能不能合：对照工作区 AGENTS.md 里的硬约定审查当前改动，按"阻断 / 建议 / 通过"分级给出结论。只读。
version: 0.1.0
argument-hint: "<分支或提交区间，默认未提交改动 + 当前分支相对 main>"
model: auto
allowed-tools:
  - run_command
triggers:
  - 帮我 review 一下这个分支
  - 看看这次改动有没有违反约定
  - 这个能合进 main 吗
not-for:
  - 发现的问题顺手修了 → implement-change
  - 写个方案 → plan-writer
tags: [dev-flow, 只读, quality]
---
# 约定审查

## 什么时候用
合并前，检查改动是否符合仓库约定。只审查、只读；run_command 只用来跑测试。

## 步骤
1. 读 `AGENTS.md`，把里面的硬约定整理成检查清单（用 `update_plan` 记下）。
2. 确定审查范围：`git_status` + `git_diff`；分支就用 `git_diff` 的 `target` 填 `main..HEAD`。
3. 逐条对照清单检查 diff；需要上下文时 `read_file`。
4. 按 `AGENTS.md` 的测试命令跑一次测试（`run_command`），失败直接算阻断。
5. 检查提交说明：对照 AGENTS.md 里的提交规范（语言、格式、内容要求），违规的算阻断项。

## 输出契约
```
结论：阻断 / 有建议可合 / 通过
阻断：
- [约定原文] 文件:行号 —— 问题
建议：
- ……
```
每条问题都要引用约定原文和具体位置，没有依据的个人偏好不算问题。

## 不要做
- 不修改任何文件，不提交
