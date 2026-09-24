---
name: rag-blueprint
version: "2.6.0"
description: "NVIDIA RAG Blueprint —— 部署、配置、排障与管理。处理任何 RAG 操作：部署（deploy）、安装（install）、启动（start）、启用（enable）、禁用（disable）、切换（toggle）、修改（change）、配置（configure）、排障（troubleshoot）、调试（debug）、修复（fix）、关停（shutdown）、停止（stop）或拆除（tear down）任何 RAG 特性或服务（Agentic RAG、VLM、guardrails、查询改写、模型、搜索、摄取、可观测性、摘要、推理等）。"
license: Apache-2.0
compatibility: >-
  需要 NVIDIA RAG Blueprint 仓库检出；部署需要 Docker/Compose 或 Kubernetes/Helm；
  库（library）工作流需要 Python 3.11+；自托管 NIM 服务需要 NVIDIA GPU 工具链。
metadata:
  author: "NVIDIA RAG <foundational-rag-dev@exchange.nvidia.com>"
  github-url: "https://github.com/NVIDIA-AI-Blueprints/rag"
  endpoint-openapi-schemas:
    - docs/api_reference/openapi_schema_rag_server.json
    - docs/api_reference/openapi_schema_ingestor_server.json
  argument-hint: 部署 RAG | 启用特性 | 禁用特性 | 配置 | 排障 | 关停
  tags:
    - nvidia
    - blueprint
    - rag
    - deployment
    - configuration
    - troubleshooting
  languages:
    - python
    - typescript
    - shell
  frameworks:
    - fastapi
    - langchain
    - react
    - docker-compose
    - helm
  domain: ai-ml
allowed-tools: Bash(echo *) Bash(nvidia-smi *) Bash(curl --version *) Bash(docker ps *) Bash(docker info *) Bash(docker --version *) Bash(docker version *) Bash(docker logs *) Bash(docker inspect *) Bash(docker stats *) Bash(docker compose ps *) Bash(docker compose logs *) Bash(docker compose config *) Bash(docker compose version *) Bash(kubectl get *) Bash(kubectl describe *) Bash(kubectl version *) Bash(kubectl logs *) Bash(kubectl api-resources *) Bash(kubectl rollout status *) Bash(helm version *) Bash(helm list *) Bash(helm status *) Bash(oc get *) Bash(oc describe *) Bash(oc logs *) Bash(oc whoami *) Bash(oc version *) Bash(git rev-parse *) Bash(git describe *) Bash(git status *) Bash(python3 --version *) Bash(pip3 show *) Bash(df *) Bash(du *) Bash(cat /proc/*) Bash(cat /etc/os-release *) Bash(ss *) Bash(netstat *) Bash(ls *) Bash(grep *) Bash(lsof *) Bash(ps aux *) Read Grep Glob
---

<!-- 中文参考译文：2026-09-22 由项目参考用途翻译，非 NVIDIA 官方版本。
     机读字段（name/version/license/metadata/tags/languages/frameworks/domain/allowed-tools）
     保持英文原值不变，避免破坏技能注册与路由；仅人读内容译为中文。 -->

# NVIDIA RAG Blueprint

## Purpose 用途

本技能用于 NVIDIA RAG Blueprint 的操作：部署、配置、排障、关停，以及跨 Docker、Helm、
库（library）三种部署形态的特性管理。

## Instructions 指令

1. 将用户请求匹配到下方的意图路由表（Intent routing table）。
2. 在动手之前，先阅读被引用的 playbook 文档。
3. 以仓库文档和部署配置文件为唯一事实来源（source of truth）。
4. 变更后验证受影响的服务或工作流。

## Prerequisites 前置条件

- NVIDIA RAG Blueprint 仓库检出（repository checkout）。
- 部署需要 Docker/Compose 或 Kubernetes/Helm。
- 库工作流需要 Python 3.11+。
- 自托管 NIM 服务需要 NVIDIA GPU 工具链。

## Autonomy Principles 自主原则

- 一切自动探测：GPU、显存、驱动、Docker、CUDA、磁盘、操作系统、端口、已有服务、NGC key、仓库状态。
- 凡是能用命令检查的，就直接检查——不要问用户。
- 只在必须用户操作时才提问：提供 API key、确认数据删除、或在多个同样合法的选项间做选择。
- 分析一完成，立即路由到正确工作流并执行。

## Intent Detection 意图识别

判定用户想要什么，并立即路由：

| 用户意图 | 动作 |
|---|---|
| 部署、安装、搭建、启动 RAG | 阅读并遵循 `references/deploy.md` |
| 配置、启用、修改、切换某特性 | 使用下方 Configure 一节 |
| 排障、调试、修复、报错、不健康 | 阅读并遵循 `references/troubleshoot.md` |
| 停止、关停、拆除、清理 | 阅读并遵循 `references/shutdown.md` |

如果意图有歧义，从上下文推断（例如 "RAG isn't working" → 排障；"get RAG running" → 部署）。
仅在确实不清楚时才提问。

---

## Configure 配置

需要 RAG 已在运行。如果服务没有运行，先通过 `references/deploy.md` 部署。

把用户请求匹配到某个参考文件，然后阅读并遵循它：

| 特性关键词 | 参考文件 |
|---|---|
| VLM、VLM 嵌入、图像captioning | `references/configure/vlm.md` |
| NeMo Guardrails | `references/configure/guardrails.md` |
| Agentic RAG、规划/执行 agent、agentic 流式、阶段事件 | `references/configure/agentic-rag.md` |
| 查询改写、问题分解、多轮 | `references/configure/query-and-conversation.md` |
| 摄取（纯文本、音频、Nemotron Parse、OCR、批量 CLI、NV-Ingest、卷挂载、性能） | `references/configure/ingestion.md` |
| 搜索、检索、混合搜索、多 collection、元数据、过滤器、Elasticsearch 过滤器、reranker、topK、准确性/性能 | `references/configure/search-and-retrieval.md` |
| LLM/嵌入/排序模型变更、向量数据库、Milvus/Elasticsearch 鉴权、服务 key、模型 profile、端口/GPU | `references/configure/models-and-infrastructure.md` |
| 推理、思考模式、`reasoning_content`、自反思、prompt、生成参数（token、温度、引用）、按请求的 LLM 参数 | `references/configure/reasoning-and-generation.md` |
| 摘要 | `references/configure/summarization.md` |
| 可观测性（追踪、Zipkin、Grafana、Prometheus） | `references/configure/observability.md` |
| 多模态查询（图像 + 文本） | `references/configure/multimodal-query.md` |
| 数据目录（collection/文档元数据） | `references/configure/data-catalog.md` |
| 用户界面（UI 设置、推理面板、元数据过滤器） | `references/configure/user-interface.md` |
| API 参考（端点、schema） | `references/configure/api-reference.md` |
| 评估（RAGAS 指标） | `references/configure/evaluation.md`（以及技能 `rag-eval`） |
| MCP 服务端与客户端、agent toolkit | `references/configure/mcp.md` |
| 迁移（版本升级） | `references/configure/migration.md` |
| Notebook（搭建与目录） | `references/configure/notebooks.md` |

### Configure Flow 配置流程

1. 把用户请求匹配到上表中的某个参考文件。

2. 探测当前运行情况：
   ```bash
   echo "=== NIM ===" && docker ps --format '{{.Names}}' 2>/dev/null | grep -iE '(nim-llm|nemotron-(vlm-)?embedding|nemotron-ranking|nemotron-vlm|nemotron-3-nano-omni|page-elements|graphic-elements|table-structure|nemotron-ocr)' || echo "NO_LOCAL_NIMS"; echo "=== RAG ===" && docker ps --format '{{.Names}}' 2>/dev/null | grep -iE '(rag-server|ingestor-server|elasticsearch|milvus|seaweedfs|lancedb)' || echo "NO_DOCKER_RAG"; echo "=== K8S ===" && kubectl get pods -n rag 2>/dev/null | head -5 || echo "NO_K8S"; echo "=== LIBRARY ===" && ps aux 2>/dev/null | grep -E '(nvidia_rag|uvicorn.*rag)' | grep -v grep || echo "NO_LIBRARY"
   ```

3. 用下表确定平台、部署类型、配置文件位置：

   | 本地 NIM 在跑？ | RAG 服务在跑？ | 部署类型 | 配置位置 |
   |---|---|---|---|
   | 是（Docker） | 任意 | 自托管 | `deploy/compose/.env` |
   | 否 | 是（Docker） | NVIDIA 托管 | `deploy/compose/nvdev.env` |
   | 是（K8s pods） | 任意 | 自托管 | `values.yaml`（NIM 段） |
   | 否 | 是（K8s pods） | NVIDIA 托管 | `values.yaml`（envVars） |
   | — | 库进程 | 库模式 | `notebooks/config.yaml` |
   | 否 | 否 | 未运行 | 先经 `references/deploy.md` 部署 |

   把你探测到的结果告诉用户并请其确认。示例："我发现本地 NIM 容器在跑（nim-llm-ms、nemotron-vlm-embedding-ms）——这是自托管部署，配置文件是 `deploy/compose/.env`。对吗？"

4. 变更前先检查特性当前状态——读取第 3 步得到的配置位置，再与线上服务交叉核对：
   - Docker：`docker exec rag-server env 2>/dev/null | grep -E "<VAR_NAME>"`
   - Helm：`kubectl get pod -n rag -l app=rag-server -o jsonpath='{.items[0].spec.containers[0].env}' 2>/dev/null`

   如果配置文件与线上服务不一致，告诉用户服务持有过期配置，需要重启。

5. 如果该特性需要额外 GPU，对照硬件限制表检查可用性（见下文）：
   ```bash
   nvidia-smi --query-gpu=index,name,memory.total,memory.used --format=csv,noheader 2>/dev/null || echo "NO_GPU"
   ```

6. 阅读参考文件并应用变更：
   - Docker：编辑 env 文件（取消注释即启用，重新注释即禁用——env 文件是唯一事实来源），然后重启受影响服务：
     ```
     source <env-file> && docker compose -f deploy/compose/<compose-file> up -d
     ```
     | 服务 | Compose 文件 |
     |---|---|
     | rag-server | `docker-compose-rag-server.yaml` |
     | ingestor-server | `docker-compose-ingestor-server.yaml` |
     | Elasticsearch、Milvus、etcd、SeaweedFS | `vectordb.yaml` |
     | NIM 容器（LLM、embedding、ranking、VLM、OCR、parse、audio、extraction） | `nims.yaml` |
     | guardrails | `docker-compose-nemo-guardrails.yaml` |
     | 可观测性（Grafana、Prometheus、Zipkin） | `observability.yaml` |
   - Helm：编辑 `values.yaml`，然后升级：`helm upgrade rag <chart> -n rag -f values.yaml`
   - 库模式：编辑 `notebooks/config.yaml`，然后重启 Python 进程

7. 验证：
   - Docker：`docker ps --format "table {{.Names}}\t{{.Status}}" | head -20; curl -s http://localhost:8081/v1/health?check_dependencies=true 2>/dev/null | head -1`
   - Helm：`kubectl get pods -n rag; kubectl rollout status deployment/rag-server -n rag --timeout=120s`
   - 库模式：`curl -s http://localhost:8081/v1/health 2>/dev/null | head -1`

8. 如果重启失败，阅读 `references/troubleshoot.md`。如果一次请求多个特性，对每个特性从第 1 步开始重复。

## Examples 示例

- "Deploy RAG"（部署 RAG）→ 路由到 `references/deploy.md`。
- "Enable VLM"（启用 VLM）→ 路由到 `references/configure/vlm.md`。
- "RAG is unhealthy"（RAG 不健康）→ 路由到 `references/troubleshoot.md`。
- "Stop RAG"（停止 RAG）→ 路由到 `references/shutdown.md`。

## Limitations 限制

- 操作指导仅适用于本 RAG Blueprint 仓库。
- 线上部署变更需要一个在跑的 Docker、Helm 或库目标。
- 诸如 `NGC_API_KEY` 之类的密钥必须由用户环境提供。

## Troubleshooting 排障

| 错误 / 信号 | 处理 |
|---|---|
| 服务没有运行 | 配置特性前先遵循 `references/deploy.md`。 |
| 重启或健康检查失败 | 遵循 `references/troubleshoot.md`。 |
| 用户要求拆除 | 遵循 `references/shutdown.md`，并确认破坏性清理。 |

### 当用户只说"配置"而没有具体说明时

运行上面的第 2–3 步，然后阅读识别出的配置文件，列出现有启用项：
```bash
grep -E "^(export )?(ENABLE_|APP_)" <config-file> 2>/dev/null | sort
```
总结当前运行与启用情况，然后询问要修改哪个特性。

---

## Hardware Restrictions 硬件限制

阅读 `docs/support-matrix.md` 获取每种部署模式当前的 GPU 要求。
阅读 `docs/service-port-gpu-reference.md` 获取端口映射与 GPU 分配。

| GPU | 特性限制 |
|---|---|
| B200 | 无 VLM、无 Guardrails、无 Nemotron Parse。LLM 可能需要多 GPU（`LLM_MS_GPU_ID`）。 |
| RTX PRO 6000 | 无 Nemotron Parse。Helm 下无音频。 |
