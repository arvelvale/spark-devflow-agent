# reference/ — 外部参考材料

本目录存放**仅供参考的第三方材料**，不是项目交付物，不参与运行，不在 README 提交内容中引用其内容为自有。

## 可视化讲解（项目自制，2026-09-22）

- `rag-blueprint-skill-可视化讲解.html`：NVIDIA rag-blueprint skill 的工作原理（三层结构 / 意图路由演示 / Configure 8 步 / 四个可抄模式）。
- `nvidia-stack-可视化讲解.html`：英伟达技术栈分层图解 v2（以图为主：七层横带可点击 / CUDA·NeMo·NIM·vLLM·OpenShell 五张剖面图 / 三条请求路径 / 节点现成资产盘点点）。事实来源见页脚。

## nvidia-skills/rag-blueprint

- 来源：https://github.com/NVIDIA/skills （`skills/rag-blueprint`，default branch main）
- 下载方式：sparse checkout（仅该 skill 目录），commit `fd9f1466ff8a39178e488981e8b5118709392949`（2026-09-18）
- 许可：Apache-2.0（仓库级）；skill-card.md 自述 owner 为 NVIDIA
- 内容：SKILL.md（v2.6.0）、skill-card.md、BENCHMARK.md、eval/（h100 / nvidia_hosted 两套评估配置）、references/（configure 16 篇 + deploy 10 篇 + troubleshoot/shutdown）、skill.oms.sig（签名）
- 参考目的：学习官方 agent skill 的设计模式（frontmatter 元数据、allowed-tools 最小权限、意图路由表、渐进式披露、检测后执行、变更后验证），对照改进本项目技能层设计。分析结论已回写 `../docs/agent架构设计.md` 第 6 节。
- 中文参考版：`SKILL.zh-CN.md`（主入口全文）与 `skill-card.zh-CN.md`（2026-09-22 项目内翻译，**非 NVIDIA 官方版本**；frontmatter 机读字段保持英文原值）。references/ 30 余篇为 NVIDIA RAG 产品操作的细节文档，未翻译。
- 可视化讲解：`rag-blueprint-skill-可视化讲解.html`（2026-09-22 制作）。- 该 skill 管理的对象是 NVIDIA RAG Blueprint（github.com/NVIDIA-AI-Blueprints/rag），与本项目产品无关；请勿将其当作可执行部署流程直接套用。
