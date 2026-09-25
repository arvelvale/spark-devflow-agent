---
name: changelog-sync
description: >-
  变更日志同步：根据提交记录按版本归类，生成或更新 CHANGELOG.md。需要写文件，执行前请用户确认。
version: 0.1.0
argument-hint: "<起始 tag 或日期，默认从上次 changelog 条目开始>"
model: auto
allowed-tools:
  - write_file
  - edit_file
  - run_command
triggers:
  - 更新一下 CHANGELOG
  - 把最近的提交整理到 changelog 里
  - 版本记录该更新了
not-for:
  - 写今天的开发日志 → progress-logger
  - 把代码改动实现一下 → implement-change
  - review 一下变更内容 → review-gate
internal: true
tags: [dev-flow, docs]
---
# 变更日志同步

## 什么时候用
用户要求把近期提交整理成 CHANGELOG.md 的版本条目，或确认变更日志与最新提交同步。需要写文件，执行前请用户确认。

## 步骤
1. `run_command` 执行 `git log --oneline <since>` 获取最近提交（`<since>` 取用户指定参数，或上次 changelog 条目对应的 tag / 日期）。
2. 按提交说明的关键词（feat / fix / docs / refactor 等）对提交归类。
3. `read_file` 读取现有 `CHANGELOG.md`（如果存在），确认格式和最后一条版本号。
4. 用 `edit_file` 在 `CHANGELOG.md` 顶部插入新版本条目；文件不存在则用 `write_file` 创建（Keep a Changelog 格式）。
5. `run_command` 执行 `git status --short`，确认只有 CHANGELOG.md 出现在改动列表里。

## 输出契约
给出变更的版本号、归类后的条目（Added / Changed / Fixed / Removed）、新增或修改的文件路径。

## 不要做
- 不编造不存在的提交或版本号
- 不改动与 changelog 无关的文件
- 不自动 git commit（写完请用户确认后决定）
