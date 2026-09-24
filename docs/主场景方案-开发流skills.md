# 主场景方案：开发流 Skills（B 方向详案）

记录日期：2026-09-22。用途：与 A 方向（改造 AdventureX）对照的**详细方案**，供方向决策。内核设计以[Agent 架构设计](agent架构设计.md)为正本，本文只定场景层，不重复内核规格。

> **2026-09-24 已定案：主线 = B。** 与下文不同的三处以架构文档 0.1 节为准：
> 1. 模型分工改为"本地为主，step-5 做难题，JEV 路由"。第 3、6 节里"vLLM+Nemotron 主 / Ollama+Qwen 备"改为"本地（两者择优，待实测）为主 + `step-5-preview` 处理难题"。
> 2. 被操作仓库改为**新建仓库**，不再用 AdventureX 做 dogfooding（第 2 节的 dogfooding 用法作废）。
> 3. 新增 Web 面板与语音输入（StepFun ASR）。
> 第 8 节原排期作废，以下方「0. 分工与 5 天排期」为准。

## 0. 分工与 5 天排期（2026-09-24 定）

### 0.1 演示资产

| 资产 | 位置 | 说明 |
|---|---|---|
| 被操作项目 | `tinyledger`（虚构的小型 Python 记账 CLI），由 `demo/seed/` 脚本生成 | 可一键重置；agent 在它上面真改代码、真跑测试 |
| Linear | Dayfire 团队 → 项目「DGX-Spark Agent 演示」（P-DAY-8） | 只放演示 issue，由种子脚本创建；key 在 `.env` 的 `LINEAR_API_KEY` |
| Obsidian | 正本 `demo/obsidian-vault/`，vault 入口 `Aerchen/项目/DGX-Spark-演示纪要`（junction） | 纪要虚构，会进外部 API，不放真实笔记 |

### 0.2 分工（4 人）

| 角色 | 负责 | 交付物 |
|---|---|---|
| 晨熠 | agent 架构 + skills 基础设计；整体集成 | 内核骨架与接口、技能规范模板（frontmatter/allowed-tools/意图路由）、7 个技能初稿、README 主体 |
| agent 优化 | 模型路由（本地 ↔ step-5）、上下文压缩、记忆、A/B 数据 | `model-router` 决策与阈值、压缩/记忆最小版、有/无 JEV 对照表 |
| 提示词优化 | 系统提示词、技能指令、JEV 问题模板（instructions/criteria） | 本地模型与 step-5 各自适配的提示词；JEV 中文问题的 confidence 分布验证 |
| skills 优化 | 技能内容打磨、负向用例、近义技能对、技能评测任务集 | 任务集（有技能/无技能/需组合三类，每类带期望决策）、技能迭代记录 |

**并行的前提**：D1 结束前冻结三个接口：技能文件格式（`skills/*/SKILL.md`）、任务集 JSON 格式、决策轨迹日志格式。之后四人互不阻塞。

### 0.3 排期（9/24–9/29，9/29 23:59 截止）

| 天 | 主线 | 验收 |
|---|---|---|
| 9/24 | 节点验证（本地两模型的工具调用、节点访问 StepFun/JEV）、仓库骨架、种子项目、三个接口冻结 | 本地模型能不能扛"本地为主"有结论；四人可开工 |
| 9/25 | 内核循环端到端（本地模型 + 工具 + JEV 技能选择）；3 个技能 v1；任务集 v1；提示词 v1 | CLI 上跑通"拆 issue"一条链 |
| 9/26 | Web 面板 + 写操作确认门控；git/Linear/Obsidian 工具接实；其余技能；路由接 step-5 | 面板上跑通"拆解 → 计划 → 改代码"三连 |
| 9/27 | 语音输入；压缩/记忆最小版；A/B harness 全量跑 | 对照数据出炉 |
| 9/28 | **功能冻结**；修 bug；演示脚本；录视频；README 部署三问 | 视频初剪完成 |
| 9/29 | 视频上传 B 站、征文、合影、表单提交；留半天缓冲 | 四项提交齐 |

**砍减顺序**（不够时从上往下砍，砍掉的在 README 里如实写"进行中"）：OpenShell → 记忆 → 上下文压缩降级为代码规则版 → 语音输入。**不许砍**：本地/step-5 路由（平台适配）、A/B 数据（技术深度）、Web 面板（完整性和演示）。

## 1. 一句话定位

> 一个跑在 DGX Spark 本地的**开发流 agent**：吃进 Linear issue、Obsidian 纪要、用户口述，经过 JEV 结构化决策层调度技能包，在 OpenShell 沙箱里调用 Git/文件/Linear 工具，产出计划、代码变更、开发日志与状态同步——全过程本地推理为主，误选率、token、耗时全部有 A/B 数据。

演示口号（评分第一项）：**把「拆解 → 开发 → 跟踪」这条开发者每天被撕碎的链路交给 agent，并且每一项结构决策都可度量、可回退。**

## 2. 与 A 方向（改造 AdventureX）的对照

| 维度 | A：改造喵灵/Morning | B：开发流 skills |
|---|---|---|
| 7 天可行性 | 全量改造不可能；只包一层"agent 化"又会变成四不像 | 内核 + 7 个技能可做最小闭环 |
| 平台展示 | RN/Harmony/StepFun，与 Spark 无关 | CUDA/vLLM/NIM/OpenShell 全部有真实岗位 |
| 技术深度证据 | 无天然评估点 | 技能误选率、token、成功率 A/B 现成 |
| 真实性 | 自己的项目，有感情分 | AdventureX 作 dogfooding 仓库，同样是真项目 |
| 结论 | **并入 B：Morning 不当改造对象，当第一个被操作的真实仓库** | **主线** |

dogfooding 的具体用法（不改造一行代码）：让 agent 在 AdventureX 仓库上真实干活——给它一个真实 issue 拆解、按它自己的日志规范写一天 progress 日志、对照它自己的 AGENTS.md 硬约定做 review。演示时这些都是真证据，不是摆拍。

## 3. 系统组成

```
                ┌──────────────── agent 内核（Spark 本地单进程）────────────────┐
                │  规划循环（vLLM+Nemotron 主 / Ollama+Qwen 备）                │
  Linear issue ─┤      ▲                                                    │─▶ 计划/代码/日志/状态
  Obsidian 纪要 ─┤      │ JEV 决策层：技能选择 · 路由 · 门控 · 置信度           │
  用户口述 ─────┤      ▼                                                    │
                │  技能包（skills/*.md，渐进式披露）                          │
                │  工具层：git · filesystem · linear · shell（受限）            │
                │  沙箱：OpenShell（策略 YAML，文件/网络/凭据/推理四道门）        │
                └──────────────────────────────────────────────────────────────┘
```

## 4. 技能包规格（7 个演示技能，交付形态 skills/*.md）

沿用 rag-blueprint 官方模式：frontmatter（name / description 前堆触发词 / argument-hint / compatibility / **allowed-tools 白名单**）+ 薄路由正文（意图表）+ references/ 按需加载。总 roster 控制在 12–15 个（演示 7 个 + 内部 5–8 个凑成"多技能选择"的真实难度，使 JEV 误选率有意义）。

| 技能 | 一句话职责 | 触发词示例 | 工具与权限 | 展示的架构点 |
|---|---|---|---|---|
| `issue-breakdown` | Linear issue/需求文档 → 结构化子任务提案 | 拆解 / 拆任务 / breakdown | linear 读、filesystem 写（草稿区） | 写操作前的确认门控 |
| `plan-writer` | 选定 issue → `docs/plans/` 实施计划（切片/验收/风险） | 写计划 / plan | filesystem 写（仓库路径内） | 遵循目标仓库规范（记忆） |
| `progress-logger` | git log/diff + 已完成 issue → 按规范写 `docs/progress/日期.md` | 写日志 / 进度 / progress | git 只读 + filesystem 写 | 多源聚合（fan-out） |
| `standup-brief` | 三源汇总 → 昨日/今日/阻塞三段简报 | 站会 / 简报 / standup | git+linear 只读 | 纯只读自动执行 |
| `review-gate` | diff 对照 AGENTS.md 硬约定分级审查（阻断/建议/通过） | review / 审查 / 检查规范 | git 只读 | Noul 门控 + Score 分级 |
| `meeting-to-tasks` | Obsidian 会议纪要 → Linear 任务草稿（确认才创建） | 纪要 / 转任务 / meeting | obsidian 读、linear 写（高阈值） | 跨知识库工具链 |
| `model-router` | 任务特征 → 路由到 Nemotron(vLLM) / Qwen(Ollama) / StepFun flash / JEV | （内部技能，不由用户直接触发） | 无外部工具 | JEV 路由决策本体 + 平台适配 |

内部凑数技能（roster 完整性用，不做深）：`branch-hygiene`、`doc-link-checker`、`test-gap-finder`、`changelog-sync`、`dependency-watch`（均来自 50 个 idea 池 A 组，每个只写索引行 + 一页说明，控制工作量）。

## 5. 工具集与权限

| 工具 | 操作 | 置信度门槛（设计值，待标定） | 沙箱策略 |
|---|---|---|---|
| git | log/diff/show/branch 等只读 | 自动执行 | 默认放行 |
| git | add/commit/push 等写 | commit ≥0.8；**push ≥0.9 且默认人工确认** | 网络默认拒绝，push 单独放行 |
| filesystem | 仓库内 + Obsidian vault 指定路径读写 | 写 ≥0.8，删/移动默认拒绝 | Landlock 白名单 |
| linear | 读 issue/list | 自动执行 | 网络仅放行 api.linear.app |
| linear | 创建/更新 issue | **一律人工确认**（外部可见写操作） | 同上 |
| shell | 测试/lint 等受限命令 | ≥0.8，白名单命令 | 沙箱内执行，输出截断回填 |

## 6. 四件套技术栈的岗位（这是评分 15% 的答卷）

| 组件 | 在本场景的岗位 | 验证状态 |
|---|---|
| CUDA | 所有本地推理的底座；部署说明里讲清驱动 580.142 / 报告 13.0 / 与推理框架的关系，不写内核 | 已在用（Ollama 走 CUDA 实测过） |
| vLLM + Nemotron-3.5-Lightning-30B-A3B-NVFP4 | **主规划/生成模型**：本地、免费、免限流 | venv 和权重现成，服务未启动（D1 验证） |
| Ollama + Qwen3.8 27B | 基线与兜底（已验证） | 已实测 |
| NIM | 「平台优化」叙事的标准化部署形态；时间紧则如实写"评估过、本次用 vLLM、playbook 已定位" | 未安装（二档验证） |
| OpenShell | agent 工具执行的沙箱 + YAML 策略（开发 agent 的刚需，最能讲故事） | 未安装（D1 验证，官方 playbook 支持 Spark） |
| JEV | 技能选择 / 路由 / 写操作门控 / 记忆精选 | key 有效，冒烟通过 |
| StepFun step-3.7-flash | 会议纪要意图识别等快速语义判断（与 JEV 搭配） | 模型名待核实 |
| NeMo Agent Toolkit | A/B 评估 harness | 未安装（一档优先） |

## 7. 演示脚本（3 分钟分镜）

1. **0:00–0:25 痛点**：开发者一天被 recount（写日志）、plan（拆计划）、sync（同步状态）撕碎；屏幕快闪三个手写场景
2. **0:25–0:55 架构一页**：本文件第 3 节那张图，标注 JEV 决策层与 OpenShell 沙箱（可视化讲解页可直接用）
3. **0:55–2:05 实跑三连**（真实录屏，不摆拍）：
   - 丢一个真实 Linear issue → `issue-breakdown` 出子任务树 → 人工确认 → 写入（展示确认门控）
   - `plan-writer` 生成实施计划 → 沙箱内改一个小文件 + 跑测试（展示 OpenShell 策略与只读/写分级）
   - `progress-logger` 按仓库规范写日志 + Linear 状态更新（展示外部写的人工确认）
4. **2:05–2:35 A/B 数据**：有/无 JEV 两臂——技能误选率、输入 token、端到耗时对照表（NAT harness 产出）
5. **2:35–3:00 平台收尾**：Spark 本地推理 + vLLM/NIM + OpenShell 四件套各一句话 + 本地 vs 外部 API 成本对比

## 8. 排期（9/22–9/29，7 天，按架构切片排）

| 天 | 内容 | 验收 |
|---|---|---|
| D1（9/22–23） | **vLLM+Nemotron 启动验证**、**OpenShell 安装验证**（两个最悬的先排）；内核 slice1 骨架 | CLI 端到端一轮本地可跑；两件套有明确可行/不可行结论 |
| D2 | slice2 技能选择（JEV 两级）+ 技能包 v1（先 3 个） | 误选/漏选对照数据 |
| D3 | slice5 门控 + git/linear/obsidian 工具真实对接 | 写操作确认链路可演示 |
| D4 | slice3 记忆最小实现（仓库约定记忆） | 记忆相关性优于关键词 |
| D5 | slice4 上下文压缩 + OpenShell 策略集成 | token 降且成功率不降 |
| D6 | NAT A/B harness 全量跑 + 演示脚本打磨 | 对照数据出炉 |
| D7 | README 脱敏版 + 录视频 + 十日谈征文 | 提交四项齐 |

**砍减预案**（时间不够按此砍，砍掉的在 README 里如实写"进行中"）：D5 压缩退化为代码规则版 → D4 记忆退化为单文件 → 内部技能从 8 个减到 5 个。**D1 两件套验证和 D6 数据不许砍**（前者是平台适配生死线，后者是技术深度证据）。

## 9. 风险与未决

1. OpenShell 安装失败 → 降级：纯代码权限分级 + tmux 隔离，README 如实写"评估过、因 X 未采用"
2. NIM 拉不到镜像（NGC 网络/架构）→ 降级：vLLM 路线 + "playbook 已定位"说明
3. Linear API token 与写入权限 → D3 前确认；没有则换文件模拟 backend（如实标注）
4. StepFun `step-3.7-flash` 模型名 → 接入时核实，失败退回 `step-3.5-flash`
5. 7 天做不完全部 → 按第 8 节砍预案执行，**禁止假装完成**（征文反而可以写"砍了什么、为什么"）
6. 技能 roster 里"近义技能对"要故意埋 1–2 组（如 `progress-logger` vs `standup-brief`）——这是 JEV 误选率数据的来源

## 10. 决策后立刻要做的三件事

1. 更新讨论文档 A2/A5：主线=B、排期按第 8 节
2. D1 启动：vLLM+Nemotron 冒烟（一条 chat completion）、OpenShell 安装（按官方 playbook，注意不改系统环境）
3. 建仓库结构：`agent/` 内核 + `skills/` 技能包 + `reference/`（已有）+ README 骨架
