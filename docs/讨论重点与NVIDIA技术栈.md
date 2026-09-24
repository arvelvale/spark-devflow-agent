# 讨论重点与 NVIDIA 技术栈

记录日期：2026-09-22。用途：**团队/组委会讨论会的议程文档**，优先讨论重点在最前面。维护正本在别处，本文只做汇总与链接：

- 赛事要求正本：[赛事要求与方案讨论](赛事要求与方案讨论.md)
- 架构设计正本：[Agent 架构设计](agent架构设计.md)
- 节点与模型运维正本：[节点连接与模型运维](节点连接与模型运维.md)

---

## A. 优先讨论重点（按讨论顺序）

### A1. 演示场景定版

- **建议**：通用内核 + 一个最小演示场景（已定方向），还需敲定场景本体。候选见架构文档第 6 节技能包设计。
- **为什么优先**：评分第一项 25% 看"实用性、行业落地价值"；场景不定，技能清单、工具集、记忆 schema 全部无法冻结，后面全是返工。
- **待定输入**：场景一句话定义 + 演示脚本三镜头。

### A2. NVIDIA 技术栈采用范围（本次讨论核心）

评分原文凭据：平台适配性 15%——"充分发挥 DGX Spark 平台的全栈能力，合理运用 NVIDIA 技术栈、开源模型和 SDK 等工具以及 StepFun 阶跃星辰模型的使用"。注意"等工具"是列举不是强制，**不能为罗列名词而引入组件**。

- **建议（分两档）**：
  - 第一档（本阶段就做）：**NeMo Agent Toolkit 做评估 harness**——纯 Python 编排层，可指向本地 Ollama，直接产出"有/无 JEV 决策层"对照数据，是技术深度 25% 的证据；风险最低。
  - 第二档（验证通过才转入演示）：**先激活节点现成的 `~/envs/vllm`（vllm 0.28.0 + torch 2.13 + flashinfer）跑 `~/models/Nemotron-3.5-Lightning-30B-A3B-NVFP4`**——零安装成本，这是"平台推理优化"最现实的演示路径；现成路线跑通并有余力，再评估 NIM / TensorRT-LLM 部署 Qwen3.8。跑不通就如实写"初期沿用 Ollama，官方 playbook 已定位步骤"。
  - 暂不引入：微调（Unsloth/NeMo/LLaMA Factory）、MIG、多机 NCCL、NVFP4 量化——只有解决具体问题且能给出评估证据时才做（沿用赛事文档既定口径）。
- **待定输入**：NGC 容器在 GB10（aarch64）上的可用性——需要在节点上按 playbook 实测，不能凭网页宣传下结论。

### A3. 多智能体与微调做不做

- **建议**：默认不做。评分项写的是"多智能体协同、模型调优深度"等**能力证明**，不是组件清单；单agent + JEV 结构化决策 + 记忆/压缩可量化收益，已经覆盖技术深度。若讨论中有人认准多智能体，要求先说清解决什么单 agent 解决不了的问题。
- **待定输入**：无（默认不做，除非出现具体问题）。

### A4. 外部 API 与提交规则（2026-09-22 更新）

- 外部 API：**用户已确认允许调用外部模型**（JEV/StepFun 外调合法）。组委会规则截图未见完整原文，建议提交前再邮件确认一次留痕，但不再作为阻塞项。
- 截止日期：**2026-09-29**（距今约一周）。最终提交资料即「项目提交要求」8 项（见 A6）。
- 仍待确认：StepFun 是否强制及指定模型/部署方式；视频时长细则；多智能体/微调是否必做（维持"列举非强制"口径）。

### A5. 排期与分工（截止日已定，需重排）

- 截止 **2026-09-29**，距今约 7 天。架构文档第 12 节的 6 个 slice **全做完不现实**，需在会上做减法。
- 建议的最小可提交集（讨论提案）：Slice 1 内核骨架 + Slice 2 技能选择（核心差异化）+ 3–5 个演示技能 + 对外脱敏 README + 3 分钟演示视频；记忆/压缩作为"进行中"如实写进征文，不假装完成。
- 征文素材从第一天开始攒（十日谈），不要最后补。
- **待定输入**：会上确认砍到哪几项、谁负责什么。

### A6. 提交物清单与交付形态（2026-09-22 依据提交要求 slide 新增）

提交要求全文已录入[赛事正本](赛事要求与方案讨论.md#项目提交要求2026-09-22-截图转录来自赛事视频-slide)。对讨论有直接约束的四条：

1. **README 是提交主载体**：500 字以上说明 + 技术方案 + 架构思路 + 部署说明 + 技术栈清单，全部在 GitHub README 体现——不是另写 Word/PDF。
2. **部署说明三问是评分抓手**：本地算力如何部署智能体、如何优化大模型、如何设计 Agent Skills。第三个问题我们的架构文档已有答案（渐进式披露 + JEV 两级选择）；第二个问题直接依赖 A2 的结论；第一个问题已有节点实录可写。
3. **skill markdown 文件必须进仓库**：技能物理形态定为 `skills/*.md`，README 索引之。这与架构第 6 节设计天然一致，无设计改动，但要提前建目录定规范。
4. **技术栈说明"用了哪个列哪个"**：NIM / TensorRT-LLM / NAT 若未验证通过，README 里只能写"已验证的 Ollama 路线 + playbook 定位记录"，不能虚标。

- **待定输入**：无（均已明确，按此执行）。

---

## B. NVIDIA 技术栈人话速览

先建立地图：**CUDA 是地基**（GPU 计算平台，驱动已自带，我们不写内核）→ **推理框架在地基上把模型跑快**（TensorRT-LLM / NIM / vLLM / SGLang / llama.cpp / Ollama）→ **训练/微调框架**（NeMo / PyTorch / Unsloth）→ **agent 与评估工具**（NeMo Agent Toolkit）。我们已站在 Ollama 这一层，往上每一层都是可选项。

| 组件 | 一句话人话 | 对本项目有什么用 | 成本/风险 | Spark playbook | 建议 |
|---|---|---|---|---|---|
| CUDA | GPU 的计算平台，驱动已含（节点报告 CUDA 13.0） | 理解驱动/推理框架关系即可 | 零 | — | 不动 |
| TensorRT-LLM | NVIDIA 官方 LLM 推理服务器，把模型编译优化后再服务 | 比 Ollama 更高吞吐/更低延迟，"平台优化"展示素材 | 必须核实 Qwen3.8 架构（GGUF Q4_K_M 权重是否需转换）与 aarch64 支持 | playbook-trt-llm | 二档验证 |
| NIM | 预打包的推理微服务（Docker 容器），拉起来即标准 API | 部署形态标准化，"全栈能力"展示素材 | 需 NGC 拉镜像（磁盘/网络），容器须支持 GB10 aarch64 | playbook-nim-llm | 二档验证，与 TRT-LLM 二选一 |
| **vLLM（节点现成）** | 开源高性能推理引擎 | **`~/envs/vllm` 已装 vllm 0.28.0 + torch 2.13.0 + triton 3.7.1 + flashinfer，`~/models` 已有配套的 Nemotron-3.5-Lightning-30B-A3B-NVFP4（21G）** | 几乎零成本：激活 venv 即用；`~/tw` 有 197 个离线 wheel 可重建环境 | playbook-vllm | **二档首选：先跑现成组合，再考虑 NIM/TRT-LLM** |
| NeMo Agent Toolkit（NAT） | agent 工作流编排 + **评估 + 性能剖析**工具链，Python | A/B 实验（有/无 JEV）、token/延迟记账，直接产出评分证据 | 纯 Python 风险低；需学它的配置格式 | 无专用 playbook，用官方文档 | **一档优先** |
| NeMo（训练框架） | 训练/微调大模型的框架 | 微调路线的前置 | 重；与节点规则（不改环境）要权衡 | playbook-nemo-fine-tune | 暂不 |
| Unsloth / LLaMA Factory | 第三方微调工具 | 微调路线 | 重 | playbook-unsloth / playbook-llama-factory | 暂不 |
| Model Optimizer + NVFP4 | 量化工具；NVFP4 是 GB10 支持的新数据格式 | 模型压缩/加速的故事素材 | 需要重做权重，与现有 GGUF 不兼容 | playbook-nvfp4-quantization | 暂不 |
| Dynamo | NVIDIA 的分布式推理服务（vLLM 生态） | 多节点扩展才有意义 | 单节点过度设计 | 无（见 vllm/sglang playbook） | 不 |
| MIG | 把一张 GPU 切多份分时复用 | 统一内存 121GiB 单模型已吃满，无切分需求 | GB10 统一内存架构下收益存疑 | playbook-mig | 不 |
| DGX Spark Playbooks | 官方步骤集（70+ 篇，Apache-2.0） | 查手册用；讨论时说"按官方 playbook 验证过" | 零 | 全部 | 用 |

**判断原则（讨论时守住的口径）**：每个组件进来必须回答"移除它我们会损失哪个可量化指标"。答不上来就不引入——这正是评分原文"合理运用"的意思，也是原始手册"遵守系统变更限制"的要求。

### 官方参考架构速查（2026-09-22 用户截图「Agents — A New Computing Platform」）

图的结构：AI Agent 居中，周围是它的"计算平台"接口——多模态输入、记忆、LLM、子代理、技能、工具（CLI/MCP）、文件、Computer Use（cuDF/cuVS + vGPU）、OpenShell 沙箱；右侧三个框是 NVIDIA 对应产品栈。逐组件作用与相关性（均已核实来源）：

| 图中元素 | 是什么（核实来源） | 在架构中的作用 | 与我们项目的相关性 |
|---|---|---|---|
| Nemotron | NVIDIA 开放模型家族（playbook「Serve Nemotron Nano and Super」；OpenShell playbook 给 DGX Station 推荐 Nemotron 3 Ultra NVFP4） | 供给 agent 的模型权重 | 低（我们用 Qwen3.8） |
| NeMo | 训练/微调 + Guardrails + Agent Toolkit 框架（官方文档已核） | 模型怎么造、agent 怎么评估 | 中（评估 harness 候选） |
| Dynamo | 推理引擎之上的编排层：disaggregated serving、KV-aware routing、KVBM 缓存卸载、SLA 自动扩缩（GitHub ai-dynamo/dynamo，Apache-2.0，8.1k stars） | LLM 服务的骨干 | **低——官方原话"单模型单 GPU，推理引擎本身就够了"** |
| NIM | 预打包推理微服务（容器） | 模型服务的标准化部署形态 | 中（A2 二档验证候选） |
| TensorRT-LLM | NVIDIA GPU 上的 LLM 推理编译优化 | 性能层，垫在 NIM/Dynamo 之下 | 中（A2 二档验证候选） |
| cuDF / cuVS | RAPIDS GPU 数据框库 + 向量检索库 | 结构化/非结构化文件的 GPU 处理与语义检索，喂给记忆层 | 低（我们的数据规模用不到 GPU 数据处理） |
| vGPU | GPU 虚拟化/切分 | Computer Use 的算力底座 | 低（单模型已吃满统一内存，与 B 节 MIG 行同理） |
| cuOpt | GPU 组合优化引擎（playbook「portfolio-optimization」） | agent 可调用的领域求解器（路径/调度/组合优化） | 低（除非演示场景是优化类） |
| OpenShell | 开源沙箱运行时：内核级隔离 + YAML 策略管控文件/网络/凭据 + 推理流量拦截路由到本地模型（playbook 全文核实，**明确支持 DGX Spark**，配 vLLM/OpenClaw） | agent 的安全边界 | **中——对应架构文档第 9 节安全与权限，可选加固路径** |
| AI-Q Research Agent | 子代理示例（研究型 agent 产品） | 演示"子代理"能力 | 参考形态 |

**结论（供 A2 讨论）**：这张图是 NVIDIA 的平台全家桶叙事，多数组件面向数据中心规模。对单节点单模型的我们，相关子集 = 本地服务层（**Ollama+Qwen3.8 已验证为基线 → 现成的 vLLM+Nemotron-3.5 NVFP4 二档首选** → NIM / TensorRT-LLM 备选）+ NeMo Agent Toolkit（评估）+ OpenShell（可选安全加固）+ rag-blueprint 式 skills 形态。另注意：`~/envs/vllm` 里已有 anthropic / openai / mcp / agent-detector 包，agent harness 可零安装起步。Dynamo / cuDF / cuVS / cuOpt / vGPU 不进本期范围，写进 README 技术栈说明时注明"评估后不采用及原因"反而是完整性加分项。

---

## C. 与架构文档的衔接

- 模型服务层不变：本地 Qwen3.8（Ollama，已验证）为主力，NIM/TRT-LLM 只可能**替换服务层实现**，不碰决策层/记忆层/skills。
- NeMo Agent Toolkit 若引入，只承担评估 harness 与 profiling，不替代自研内核（内核是我们的差异化，NAT 是裁判）。
- 隐私边界不变：NAT 评估与 NIM/TRT-LLM 都属于本地或容器内组件，StepFun/JEV 的外调清单不变。

---

## D. 待补充与待确认

1. ~~截图内容占位~~ 已补齐：2026-09-22 拿到「项目提交要求」slide 全文，已录入赛事正本并派生 A6。当年截图的视频中如还有其它 slide，拿到后续补。
2. 组委会确认（2026-09-22 部分解决）：外部 API 已确认允许、截止 2026-09-29、提交形态已明确；仍剩 StepFun 强制性、视频时长细则（见 A4）。
3. 节点侧实测项：NIM/TRT-LLM 容器在 GB10 aarch64 的可用性（按 playbook，注意不改系统环境、不重启、磁盘留 20%）。

---

## 附：候选方向分析与 50 个 idea 池（2026-09-22 用户提问）

### 用户提出的两个方向

| 方向 | 内容 | 评估 |
|---|---|---|
| A. 把 AdventureX（喵灵/Morning）转成 agent+skills 形态 | 已上线的情感陪伴 App（RN+FastAPI+LangGraph+ deployed 后端） | **不建议作主线**：全量改造 scopes 巨大、7 天内做不完；且其技术栈（RN/Harmony/StepFun）与 DGX Spark 平台展示无关，评分收益低。但其是**绝佳的 dogfooding 标的**：真实 git 仓库 + 开发日志 + plans + specs + AGENTS.md 约定 |
| B. 做一套「开发流 skills」：agent 通过 Obsidian + Linear + Git 完成项目拆解 → 开发 → 状态跟踪 | 多 skill 包 + 工具调用 + 跨会话记忆 + 长会话压缩 | **建议主线**：与已研读的 rag-blueprint 官方形态同构（技能多 → JEV 两级选择有戏）；git 写操作天然需要 OpenShell 沙箱与 confidence 门控；长开发会话天然需要上下文压缩；四件套技术栈（CUDA/vLLM/NIM/OpenShell）全部有真实岗位 |

**推荐组合**：B 为主线，AdventureX 作为第一个被操作的真实仓库（不改造它，让 agent 在它身上干活——如生成 progress 日志、拆计划、巡检约定）。内核仍按架构文档切片先行，技能包随后。

> 详细方案（技能包规格、工具权限、四件套岗位、演示分镜、7 天排期、砍减预案）见 [主场景方案-开发流skills](主场景方案-开发流skills.md)。用户 2026-09-22 选择「先看详细方案再定」。

### 50 个候选 idea（按考察点分组）

**A 组 · 开发流技能族（B 方向本体）**

1. `project-breakdown`：需求文档 → Linear 史诗/任务/子任务 + 验收标准
2. `daily-standup`：git log + Linear 状态 + 开发日志 → 昨日/今日/阻塞简报
3. `progress-log`：当天 git diff + 已完成 issue → 按仓库日志规范写 `docs/progress/YYYY-MM-DD.md`
4. `plan-writer`：为选中 issue 写 `docs/plans/` 实施计划（切片/验收/风险）
5. `code-review-gate`：diff 对照 AGENTS.md 硬约定审查（分级：阻断/建议/通过）
6. `release-notes`：两 tag 间 git log → 面向用户的 release notes（feat/fix/breaking 分类）
7. `issue-triage`：新 issue 定型/定优先级/估时/建议归属
8. `conventions-keeper`：AGENTS.md 约定与实际代码一致性巡检（Morning 有文档漂移前科）
9. `changelog-sync`：CHANGELOG 与 git tag 对齐检查
10. `onboarding-buddy`：新成员「怎么跑起来」→ 从 README/AGENTS.md/scripts 组装答案
11. `spec-drift-detector`：`.kiro/specs` 与实现的漂移检测
12. `merge-conflict-advisor`：冲突文件的语义级合并建议
13. `test-gap-finder`：找「改了没测」的文件并建议测试点
14. `dependency-watch`：npm/pip 依赖过期与 CVE 简报
15. `doc-link-checker`：文档链接/锚点有效性巡检
16. `meeting-to-tasks`：Obsidian 会议纪要 → Linear 任务草稿（人确认才创建）
17. `weekly-review`：一周 git+Linear+日志 → 周报（十日谈征文素材）
18. `branch-hygiene`：陈旧分支/未合并 PR 清理建议
19. `hotfix-flow`：报障 → 定位引入提交 → 修复分支 + 回归清单
20. `api-contract-diff`：`api-design.md` 标记与路由实现的差异

**B 组 · JEV 决策层高光场景（选择/评分密集）**

21. `model-router`：按任务/成本/延迟路由本地 Nemotron/Qwen/StepFun——JEV 做路由本体
22. `email-triage`：分类+紧急度+建议动作（官方 support triage 变体）
23. `resume-screen`：简历×JD 多因子分解评分（composite scoring 示范）
24. `news-filter`：信息流按兴趣打分过滤（Noul 门控）
25. `contract-review`：合同条款风险分级（只读）
26. `bug-severity`：严重度/沮丧度/可复现性多维分解
27. `translation-qa`：译文质量分维度评分
28. `prompt-injection-guard`：入站/出站安检（Noul+Score 官方配方）
29. `citation-checker`：引用与出处核对（防幻觉引用）
30. `dedupe-decider`：重复 issue/笔记合并判定
31. `backlog-prioritizer`：价值/成本/风险/依赖多因子排序
32. `tag-normalizer`：标签体系统一（闭集 Choice）

**C 组 · 记忆与压缩收益场景**

33. `research-digest`：多篇资料 → 结构化摘要+证据链
34. `book-notes`：读书卡片抽取（Zettelkasten 式）
35. `meeting-memory`：纪要入库+待办提取
36. `codebase-memory`：大仓库结构/约定压缩为可复用记忆
37. `chat-archivist`：长会话归档+可检索摘要
38. `knowledge-gap`：知识库 vs 问题域的缺口分析

**D 组 · 平台/工程展示（Spark/vLLM/NIM/CUDA/OpenShell）**

39. `gpu-doctor`：nvidia-smi/驱动/显存只读诊断
40. `model-benchmark-runner`：Nemotron vs Qwen、vLLM vs Ollama 延迟吞吐基准
41. `nim-deployer`：NIM 容器部署与健康检查（对标 rag-blueprint 形态）
42. `openshell-policy-writer`：为 agent 工具调用生成最小权限 YAML 策略
43. `inference-cost-accountant`：token/耗时/费用账本
44. `spark-capacity-planner`：显存/磁盘余量下的模型选型建议
45. `trace-analyzer`：Nsight 剖析结果人话解读
46. `offline-wheelhouse-check`：断网依赖重建检查（节点现成资产）

**E 组 · 日常实用（差异化备选）**

47. `study-coach`：考试复习计划与考点预测
48. `market-digest`：行情/资讯简报（结论+概率先行）
49. `meal-planner`：按库存/预算/忌口的周菜单
50. `trip-planner`：多约束行程规划（预算/时间/偏好打分）

### 从 50 里选演示组合的建议

主线 B 的演示技能包取 **1/2/3/5/16/21/42** 七个：覆盖「拆解→开发→跟踪」全链路 + JEV 路由 + OpenShell 策略；其中 21（model-router）同时是平台适配证据。记忆（36）与压缩（22/37）作为架构组件单独展示，不挤占技能包名额。

## 验证状态

playbook 清单来自 github.com/NVIDIA/dgx-spark-playbooks（2026-09-22 抓取，1.4k stars，Apache-2.0）；NeMo Agent Toolkit 依据官方文档 1.8 版目录结构（含 Using Local LLMs、Evaluate Workflows、Profiler 页面）。提交要求 slide 全文来自用户 2026-09-22 截图（图像输入已可正常读取）。Dynamo 依据 GitHub ai-dynamo/dynamo README（Apache-2.0）；OpenShell 依据 playbook-openshell 全文（含"明确支持 DGX Spark、配 vLLM/OpenClaw"）。节点预装清单来自 2026-09-22 SSH 实测（`~/envs/vllm`、`~/models/Nemotron-3.5-Lightning-30B-A3B-NVFP4`、`~/tw` wheelhouse 等，详见运维正本）。AdventureX 判断来自仓库 README/AGENTS.md 实读（未运行其代码）。本节所有"建议"均为讨论提案；**vLLM venv 与 Nemotron 权重虽已存在，但尚未启动服务验证**；NIM/TensorRT-LLM/NAT/OpenShell 均未安装、未运行。
