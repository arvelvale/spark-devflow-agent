<!-- 中文参考译文：2026-09-22 翻译，非 NVIDIA 官方版本。 -->

## Description 描述 <br>
NVIDIA RAG Blueprint —— 跨 Docker Compose、Helm 与库（library）部署的 RAG 流水线部署、配置、排障与管理。<br>

本技能可用于商业/非商业用途。<br>

## Owner 归属方 <br>
NVIDIA <br>

### License/Terms of Use 许可/使用条款 <br>
Apache 2.0 <br>
## Use Case 适用场景 <br>
使用 Docker、Helm 或 Python 库工作流部署、配置、排障和管理 NVIDIA RAG Blueprint 流水线的开发者与工程师。<br>

### Deployment Geography for Use 部署地域 <br>
全球 <br>

## Known Risks and Mitigations 已知风险与缓解 <br>
风险：执行前需审阅——skill 提案可能把不正确或有误导性的指导引入技能。<br>
缓解：部署前审阅并扫描该技能。<br>

## Reference(s) 参考 <br>
- [NVIDIA RAG Blueprint GitHub](https://github.com/NVIDIA-AI-Blueprints/rag) <br>
- [部署指南](references/deploy.md) <br>
- [排障](references/troubleshoot.md) <br>
- [关停](references/shutdown.md) <br>
- [Agentic RAG](references/configure/agentic-rag.md) <br>
- [Guardrails](references/configure/guardrails.md) <br>
- [模型与基础设施](references/configure/models-and-infrastructure.md) <br>
- [搜索与检索](references/configure/search-and-retrieval.md) <br>
- [可观测性](references/configure/observability.md) <br>
- [MCP 服务端与客户端](references/configure/mcp.md) <br>

## Skill Output 技能输出 <br>
**输出类型：** [Shell 命令、配置说明、诊断分析] <br>
**输出格式：** [Markdown，内联 bash 代码块] <br>
**输出参数：** [1D] <br>
**其他输出相关属性：** [无] <br>

## Evaluation Tasks 评估任务 <br>
NVSkills-Eval 三级评估（external profile）：9 项静态校验（Tier 1）与 2 项去重校验（Tier 2）。本报告中 Tier 3 线上 agent 评估不可用。<br>

## Evaluation Metrics Used 所用评估指标 <br>
报告基准维度：<br>
- 安全（Security）：检查带技能的执行是否避免不安全行为，如密钥泄露、破坏性命令、未授权访问。<br>
- 正确性（Correctness）：检查 agent 是否遵循预期工作流并产出正确的最终输出。<br>
- 可发现性（Discoverability）：检查 agent 是否在相关时加载技能、不相关时不使用。<br>
- 有效性（Effectiveness）：检查 agent 带技能时是否显著优于不带。<br>
- 效率（Efficiency）：检查 agent 是否使用更少 token 并避免冗余工作。<br>

## Skill Version(s) 技能版本 <br>
2.6.0（来源：frontmatter）<br>

## Ethical Considerations 伦理考量 <br>
NVIDIA 认为可信 AI 是共同责任，并已建立相应政策与实践，使开发者能在广泛的阵列用例中开发。按照服务条款下载或使用时，开发者应与内部团队协作，确保该技能满足相关行业用例的要求，并应对预见之外的产品滥用。<br>

（仅在 NVIDIA 平台发布）<br>
请通过[此处](https://app.intigriti.com/programs/nvidia/nvidiavdp/detail)报告质量、风险、安全漏洞或 NVIDIA AI 相关问题。<br>
