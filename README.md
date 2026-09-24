# DGX Spark 开发流 Agent

跑在 NVIDIA DGX Spark 上的开发流 agent：读 Linear issue、Obsidian 纪要和用户口述，完成"拆解 → 计划 → 开发 → 写日志 → 同步状态"。
所有"选哪个"的结构化判断（技能选择、模型路由、工具门控、记忆精选、上下文压缩）交给 JEV 决策层，并且每个决策都写进可度量的决策轨迹。

> 这是团队内部 README。参赛提交用的对外版本（500 字说明、部署三问、技术栈清单）在截止前另写。

## 架构一览

```
输入 → 技能选择（JEV 两级）→ 模型路由（本地 Nemotron / 云端 step-5）→ 记忆精选
     → 规划循环：[压缩检查 → 主模型 → 工具门控 → 执行 → 回填] × N → 回复
     → 记忆写回 → 决策轨迹
```

| 层 | 组件 |
|---|---|
| 本地推理 | vLLM 0.28 + Nemotron-3.5 30B-A3B NVFP4（约 80 tok/s，主力）；Ollama + Qwen3.8 27B（备用） |
| 云端推理 | StepFun `step-5-preview`（写代码、复杂规划） |
| 决策层 | JEV（TypeSafe `jev-latest`） |
| 工具 | 文件、git、白名单命令、Obsidian、Linear |

设计正本：[docs/agent架构设计.md](docs/agent架构设计.md)；场景与排期：[docs/主场景方案-开发流skills.md](docs/主场景方案-开发流skills.md)。

## 目录

```
agent/            内核（每个模块文件头都写了职责和设计依据）
  tools/          工具实现；新增工具就在对应模块的 TOOLS 里加一项
skills/*/SKILL.md 技能（格式见 docs/接口/01-技能文件格式.md）
eval/             任务集、技能选择 A/B、门控标定
demo/             演示种子：tinyledger 仓库生成、Linear 演示 issue、Obsidian 纪要
docs/接口/        三个接口契约：技能文件 / 任务集 / 决策轨迹
scripts/node.py   同步到节点、带隧道执行
tests/            单元测试（不访问网络）
```

## 快速开始

```bash
pip install pyyaml pytest            # 唯一的运行依赖是 pyyaml
python -m pytest                     # 单元测试
python demo/seed/make_workspace.py   # 生成演示仓库到 var/workspace/tinyledger
python -m agent doctor               # 检查模型、JEV、Linear、工作区
python -m agent chat                 # 交互对话；写操作会逐条请你确认
python -m agent run "待会开站会，帮我理一下昨天干了啥今天干啥"
```

密钥放在根目录 `.env`（已 gitignore）：`STEPFUN_API_KEY`、`TYPESAFE_API_KEY`、`LINEAR_API_KEY`。
本机运行时本地模型要走 SSH 隧道（`-L 8000:127.0.0.1:8000 -L 11434:127.0.0.1:11434`）。

在节点上跑（推荐，本地模型直连）：

```bash
python scripts/node.py sync
python scripts/node.py run "python3 -m agent doctor"
```

节点直连不了境外，JEV 和 Linear 经 SSH 反向隧道走操作机代理，所以**操作机要在线**。详见 [docs/节点连接与模型运维.md](docs/节点连接与模型运维.md)。

## 分工入口

| 角色 | 主要改哪里 | 怎么验证 |
|---|---|---|
| 架构 / skills 基础设计 | `agent/`、`docs/接口/` | `python -m pytest` |
| agent 优化 | `agent/router.py`、`agent/context.py`、`agent/memory.py`、`agent/config.py` 里的阈值 | `python -m eval.run_selection`，节点上跑真实场景看 `var/runs/*/trace.jsonl` |
| 提示词优化 | `agent/prompts.py`、各模块里的 JEV 问题措辞（`gate_questions()` 等） | `python -m eval.run_gate`、`python -m eval.run_selection` |
| skills 优化 | `skills/*/SKILL.md`、`eval/tasks/*.json` | `python -m agent skills`、`python -m eval.run_selection` |

改阈值前先读 `agent/config.py` 里每个阈值的方向注释（值越大意味着什么），改完跑一遍对应的评估。

## Web 面板

```bash
python scripts/node.py sync      # 先在 web/ 里 npm install && npm run build，sync 会把 web/dist 一起带上
python scripts/node.py serve     # 节点上起面板 + 本机 127.0.0.1:9000 转发；Ctrl+C 结束，节点进程随之退出
```

浏览器打开 http://127.0.0.1:9000，口令是 `.env` 里的 `AGENT_WEB_TOKEN`（没设就每次随机生成并打印在终端）。

- 左栏：会话（含命令行跑过的历史会话，只读回放）、长期记忆、服务状态灯（绿 运行 / 蓝 备用 / 琥珀 异常 / 灰 离线）
- 中间：对话；每轮下面一条决策摘要（技能 · 本地/云端 · 步数 · 耗时），写操作在这里弹确认卡
- 右栏：所选轮次的决策轨迹（技能两级概率与阈值、路由难度、记忆精选、每步工具与门控、用量）和工作记忆
- 语音：点麦克风说话 → 转成文字进输入框，可以先改再发。**浏览器只在 localhost 或 https 下开放麦克风**

前端开发：`cd web && npm run dev`（5173 端口，/api 代理到 127.0.0.1:9000）。自测截图：`node web/scripts/shot.mjs <URL> out.png [--dark] [--w 390 --h 844]`。
`python -m agent serve --dev-no-auth` 可免登录，但只允许配合回环地址；挂公网（`serve --public`，监听 0.0.0.0:9000 → 节点公网地址的 9006，以登录表为准）一律要口令。

## 常用参数

- `--no-jev`：关掉 JEV 决策层（A/B 的基线臂）
- `--tier local|cloud`：强制模型档位
- `--yes`：写操作自动确认，**只在演示沙盒里用**
- 环境变量：`AGENT_CONTEXT_BUDGET`（压缩预算）、`AGENT_LOCAL_THINKING=0`（本地主循环关思考）、`AGENT_MEMORY_EXTRACT=0`（关记忆抽取）
