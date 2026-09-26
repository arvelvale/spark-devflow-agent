---
name: standup-brief
description: >-
  站会 / 简报 / 汇报 / 昨天干了啥 / standup：汇总提交、Linear 和纪要，生成"昨日完成 / 今日计划 / 阻塞"三段口头简报。只在对话里回复，不写文件，不改 Linear 状态。
version: 0.2.1
model: local
allowed-tools: []
scripts:
  - name: collect.py
    description: 一次收齐最近提交、未提交改动、当前分支、最近一份纪要的待办和未决事项
    permission: read
    args: "[天数，默认 1]"
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
1. `run_skill_script` 跑 `collect.py`（周一或用户说"这几天"就传天数，比如 `["3"]`），一次拿到提交、未提交改动和纪要待办。
2. `linear_list_issues` 看进行中和待办的 issue（脚本不碰 Linear）。
3. 脚本出错时退回逐个工具：`git_log` / `git_status` / `list_notes` + `read_note`。
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
