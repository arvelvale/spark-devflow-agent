# AGENTS.md — tinyledger 约定

人和 agent 都按这里的约定干活。

## 代码
1. 只用 Python 标准库，不引入第三方依赖。
2. 新增或修改命令时，同步更新 README 的用法小节。
3. 改代码必须跑测试且全部通过：`python -m unittest`。
4. 修 bug 要先补一个能复现问题的测试。

## 提交
5. 提交说明用中文，一句话说清做了什么；关联 issue 时把编号写在末尾，如 `修复合计精度 (DAY-7)`。
6. 不直接在 main 上开发，功能分支命名 `<人名或 agent>/<短名>`。

## 文档
7. 开发日志：`docs/progress/YYYY-MM-DD.md`，标题 `# YYYY-MM-DD 开发日志`，固定三个小节「完成」「进行中」「问题」，每条末尾附提交短哈希或 issue 编号。
8. 实施计划：`docs/plans/YYYY-MM-DD-<英文短名>.md`。
