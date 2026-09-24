"""DGX Spark 开发流 agent 内核。

模块分工（详见 docs/agent架构设计.md）：
- config    端点、模型、阈值
- llm       OpenAI 兼容的对话客户端（本地 vLLM / Ollama、云端 StepFun）
- decision  JEV 决策客户端（缓存、退避、降级）
- router    本地 ↔ step-5 路由
- skills    技能加载、校验、两级选择
- tools     工具注册表与各工具实现
- gate      工具门控（权限级别 × JEV 判断）
- memory    长期记忆（SQLite）与精选、写回
- context   工作记忆、上下文压缩、原文归档
- trace     决策轨迹（JSONL）
- kernel    把以上串成一轮 turn
"""

__version__ = "0.1.0"
