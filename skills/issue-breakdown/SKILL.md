---
name: issue-breakdown
description: >-
  拆解 / 拆任务 / 拆子任务 / breakdown：把一个 Linear issue 或一段需求拆成可独立完成的子任务（每条带验收标准），经用户确认后作为子 issue 写回 Linear。
version: 0.1.0
argument-hint: "<issue 编号，如 DAY-5；或一段需求文字>"
model: auto
allowed-tools:
  - linear_get_issue
  - linear_list_issues
  - linear_create_issue
triggers:
  - 把 DAY-5 拆一下
  - 这个需求帮我拆成子任务，建到 Linear 上
  - CSV 导出这个 issue 太大了，拆成几步
not-for:
  - 给 DAY-5 写一份实施计划 → plan-writer
  - 把会议纪要里的待办变成任务 → meeting-to-tasks
tags: [dev-flow, linear]
---
# 拆解 issue

## 什么时候用
用户要把一个 issue 或需求拆成更小的、可以分别完成和验收的子任务。

## 步骤
1. 用 `linear_get_issue` 读原 issue（描述、已有子任务、评论）。用户给的是一段文字就以它为准。
2. 用 `search_text` / `read_file` 看相关代码，确认拆分贴合实际代码结构；读工作区的 `AGENTS.md` 了解约定。
3. 用 `update_plan` 写下目标和拆解思路。
4. 拆成 2–6 个子任务。每个子任务要满足：
   - 一个人半天到一天能完成
   - 有明确的验收标准（可运行的命令或可观察的行为）
   - 标注依赖（哪个要先做）
5. 已有同名或同义的子任务就不要重复建。
6. 用户只说"拆一下"时：先在回复里给出提案，问要不要写回 Linear。
   用户明确说"建到 Linear 上"时：逐条调用 `linear_create_issue`（填 `parent`），系统会请用户确认每一条。
7. 一次最多只建 1 个主任务。其余子任务作为提案在回复里列出，等用户明确说"建到 Linear 上"再逐条调用 `linear_create_issue`。

## 输出契约
回复里给一个表格：序号 / 子任务标题 / 验收标准 / 依赖。已创建的写上新 issue 编号。

## 不要做
- 不改原 issue 的标题和描述
- 不给子任务设负责人（没有这个工具，也不该替团队决定）
