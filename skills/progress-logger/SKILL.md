---
name: progress-logger
description: >-
  写日志 / 开发日志 / 进度记录 / progress：汇总当天的 git 提交和完成的 issue，按仓库规范写成 docs/progress/日期.md 日志文件。
version: 0.1.0
argument-hint: "<日期，默认今天>"
model: local
allowed-tools:
  - write_file
  - edit_file
  - git_commit
triggers:
  - 把今天改的几个提交整理一下，落到 docs/progress 里
  - 写一下今天的开发日志
  - 补一下 9 月 23 号的进度记录
not-for:
  - 待会站会，帮我理一下昨天干了啥 → standup-brief
  - 把 Linear 上的状态更新一下 → status-sync
tags: [dev-flow, docs, 近义组]
---
# 写开发日志

## 什么时候用
用户要把某一天的开发进展**写成文件**留档。只是口头汇报（站会）用 standup-brief。

## 步骤
1. 读 `AGENTS.md` 里的日志规范（文件位置、标题格式、必须有的小节）。
2. `git_log`（`since` 设为目标日期，`stat` 为 true）拿当天提交；必要时 `git_show` 看具体改动。
3. `linear_list_issues` 看哪些 issue 在当天变成 Done 或有进展。
4. 目标日期的日志文件已存在就追加（`edit_file`），不存在就新建（`write_file`）。
5. 内容只写有证据的事：每条对应一个提交哈希或 issue 编号。
6. 用户要求提交时才 `git_commit`。

## 输出契约
回复给出日志文件路径和条目数，并列出没法归到任何提交或 issue 的内容（如果有）。

## 不要做
- 不编造没有提交记录的工作
- 不改 Linear 状态（交给 status-sync）
