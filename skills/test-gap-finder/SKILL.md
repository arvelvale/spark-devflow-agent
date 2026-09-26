---
name: test-gap-finder
description: >-
  测试缺口检查：分析当前 diff 或指定文件里未被测试覆盖的分支路径，给出建议补测的位置。只读，不修改任何内容。
version: 0.1.1
argument-hint: ""
model: local
allowed-tools: []
triggers:
  - 检查一下测试缺口
  - 哪些代码没有被测试覆盖
  - 看看还有哪些分支没测到
not-for:
  - 补写缺失的测试 → implement-change
  - review 一下测试质量 → review-gate
internal: true
tags: [dev-flow, 只读]
---
# 测试缺口检查

## 什么时候用
用户想了解当前代码库哪些路径缺少测试覆盖，或补测前的定位。只读分析，不改文件、不提交。

## 步骤
1. `code_outline` 看测试目录（一般是 `tests/`），拿到已有测试函数列表。纯静态分析，不运行测试。
2. 确定范围：用户指定了文件就用它；否则用 `git_diff`（未提交改动）或 `git_diff` 的 `target` 填 `main..HEAD`。
3. 对范围内的模块用 `code_outline` 列出函数；对每个函数用 `find_symbol` 看测试里有没有引用它。
4. 被测试引用到的函数，用 `read_file` 按行号读函数体，找测试里没出现的分支条件（if/elif/else、异常处理）。
5. 按缺口严重程度排序：完全没测试的函数 > 有测试但缺分支覆盖的函数 > 异常路径未测。

## 输出契约
给出缺口列表：文件路径 / 函数名 / 缺失类型（无测试 / 缺分支 / 缺异常）/ 建议补测的用例方向。按优先级排序。

## 不要做
- 不自动补写测试文件
- 不修改任何代码或测试
- 不运行测试验证（只做静态分析）
