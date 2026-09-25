---
name: standup-brief
description: >-
  站会 / 简报 / 汇报 / 昨天干了啥 / standup：汇总提交、Linear 和纪要，生成"昨日完成 / 今日计划 / 阻塞"三段口头简报。只在对话里回复，不写文件，不改 Linear 状态。
version: 0.1.0
model: local
allowed-tools: []
triggers:
  - 待会开站会，帮我理一下昨天干了啥今天干啥
  - 给我个 standup 简报
  - 现在卡在哪些事情上
not-for:
  - 把今天的进展写进 docs/progress → progress-logger
  - 把 Linear 状态同步一下 → status-sync
tags: [dev-flow, 只读, 近义组]
---
# 站会简报

## 什么时候用
用户要一段能直接念出来的进度汇报。纯只读，不写文件、不改任何状态。

## 步骤
1. `git_log`（since 昨天）看提交；`git_status` 看是否有未提交的改动。
2. `linear_list_issues` 看进行中和待办的 issue。
3. `list_notes` 找最近一次会议纪要，读里面的待办和"没定的"。
4. 归纳成三段。

## 输出契约
```
昨日完成：
- ……（附提交哈希或 issue 编号）
今日计划：
- ……
阻塞 / 需要讨论：
- ……（没有就写"无"）
```
总长度控制在 200 字内，适合口头念。

## 不要做
- 不写任何文件（要留档用 progress-logger）
