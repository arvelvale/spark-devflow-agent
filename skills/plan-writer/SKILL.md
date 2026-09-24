---
name: plan-writer
description: >-
  写计划 / 实施计划 / 方案 / plan：为一个选定的 issue 写实施计划文档（切片、验收、风险、涉及文件），存到工作区 docs/plans/。
version: 0.1.0
argument-hint: "<issue 编号或功能名>"
model: auto
allowed-tools:
  - write_file
  - edit_file
triggers:
  - 给 DAY-6 写个实施计划
  - 金额精度这个问题怎么改，先出个方案文档
  - 月度汇总准备开工了，写一下 plan
not-for:
  - 把 DAY-6 拆成子任务建到 Linear → issue-breakdown
  - 直接把这个功能实现了 → implement-change
tags: [dev-flow, docs]
---
# 写实施计划

## 什么时候用
开工前，把"要做什么、怎么切、怎么验收、有什么风险"写成一份计划文档。只写计划，不改代码。

## 步骤
1. 读 issue（`linear_get_issue`）或用户描述，读工作区 `AGENTS.md` 里关于计划文档的约定。
2. 读相关代码（`search_text` / `read_file`），列出真正会动到的文件。
3. 写到 `docs/plans/<今天日期>-<英文短名>.md`，结构：
   - 背景与目标（引用 issue 编号）
   - 方案（关键设计决定及理由；有取舍就写出放弃的方案）
   - 切片：每片可以单独提交、单独验收；写清每片的验收命令
   - 涉及文件
   - 风险与回滚（例如数据格式变更要怎么兼容老数据）
4. 写完用 `read_file` 回读一遍确认格式。

## 输出契约
回复给出计划文件路径和切片清单（一行一片）。

## 不要做
- 不改源代码，不提交（交给 implement-change）
- 不编造不存在的文件或函数，没看过的代码不要写进"涉及文件"
