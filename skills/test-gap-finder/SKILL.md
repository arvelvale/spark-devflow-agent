---
name: test-gap-finder
description: >-
  测试缺口检查：分析当前 diff 或指定文件里未被测试覆盖的分支路径，给出建议补测的位置。只读，不修改任何内容。
version: 0.1.0
argument-hint: ""
model: local
allowed-tools:
  - run_command
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
1. `run_command` 执行测试命令（一般是 `python -m pytest --co -q` 或 `python -m unittest discover`）收集已有测试列表。
2. `run_command` 执行 `git diff --name-only` 或读取用户指定的文件路径，确定待分析范围。
3. 对范围内的每个模块，用 `search_text` 查找关键函数和分支条件（if/elif/else、异常处理）。
4. 交叉比对：哪些函数有对应测试文件、哪些分支条件在测试里没有出现。
5. 按缺口严重程度排序：完全没测试的函数 > 有测试但缺分支覆盖的函数 > 异常路径未测。

## 输出契约
给出缺口列表：文件路径 / 函数名 / 缺失类型（无测试 / 缺分支 / 缺异常）/ 建议补测的用例方向。按优先级排序。

## 不要做
- 不自动补写测试文件
- 不修改任何代码或测试
- 不运行测试验证（只做静态分析）
