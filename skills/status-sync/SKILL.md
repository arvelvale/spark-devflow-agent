---
name: status-sync
description: >-
  同步状态 / 更新 Linear / 关 issue / sync：根据提交记录和测试结果，把 Linear issue 的状态和进展评论同步到最新。只改 Linear，不写日志文件，不生成口头总结。
version: 0.1.0
argument-hint: "<issue 编号，默认检查演示项目里所有进行中的 issue>"
model: local
allowed-tools:
  - linear_update_issue
triggers:
  - 金额精度修完了，去 Linear 上把状态改一下
  - 同步一下 Linear 上的进度
  - 把 DAY-7 关掉，附上提交记录
not-for:
  - 写今天的开发日志 → progress-logger
  - 站会前理一下进度 → standup-brief
tags: [dev-flow, linear, 近义组]
---
# 同步 Linear 状态

## 什么时候用
代码已经有进展，需要让 Linear 上的状态反映实际情况。

## 步骤
1. `linear_list_issues` / `linear_get_issue` 看当前状态。
2. `git_log` / `git_show` 找对应的提交（提交说明或分支名里带 issue 编号的优先）。
3. 判断目标状态，**必须有证据**：
   - 有提交且测试通过 → Done（附提交哈希）
   - 有提交但没完成 → In Progress（评论写做到哪了）
   - 没有任何提交 → 不改状态
4. 调用 `linear_update_issue`，评论里写：做了什么、对应提交、验证方式。系统会请用户确认。

## 输出契约
回复给出一张表：issue / 原状态 / 新状态 / 依据（提交哈希）。没改的也列出来并说明原因。

## 不要做
- 没有证据不改状态
- 不创建新 issue（那是 issue-breakdown 或 meeting-to-tasks 的事）
