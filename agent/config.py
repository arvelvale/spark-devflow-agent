"""运行配置。优先级：环境变量 > 项目根 .env > 默认值。

阈值全部是**设计值**（官方 cookbook 起始值或保守拍定值），要在任务集上标定后再改。
每个阈值旁边写清楚"值越大意味着什么"，防止方向写反。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """把 .env 注入 os.environ；已存在的环境变量优先。不打印任何值。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Endpoint:
    """一个 OpenAI 兼容的对话服务。"""

    name: str                      # local / backup / cloud
    base_url: str
    model: str
    api_key_env: str = ""          # 空 = 不需要鉴权（本地服务）
    use_proxy: bool = False        # True = 走 https_proxy（节点上经 SSH 反向隧道出境）
    max_concurrency: int = 4
    timeout: float = 180.0
    extra: dict = field(default_factory=dict)  # 附加到请求体的字段

    @property
    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "") if self.api_key_env else ""

    @property
    def configured(self) -> bool:
        return not self.api_key_env or bool(self.api_key)


@dataclass
class Thresholds:
    # ---- 技能选择（架构 3.3a）----
    # gate = 三个门控 Noul 的均值，越大越说明"这句话需要技能"。gate < skill_gate → 不推荐任何技能。
    skill_gate: float = 0.30
    # 第二级每个候选一个 fits Noul，越大越合适。最高 fits < skill_fit → 全部拒绝。
    skill_fit: float = 0.30
    # 其余候选 fits ≥ skill_multi → 作为附加技能一起加载（组合技能）。
    skill_multi: float = 0.70
    skill_stage2_topk: int = 3
    # ---- 记忆精选（架构 3.3b）----
    # relevant 越大越相关。≥ memory_full → 原文进上下文；[memory_brief, memory_full) → 只放一行；更低丢弃。
    memory_full: float = 0.70
    memory_brief: float = 0.40
    memory_recall_k: int = 8
    # ---- 记忆写入 ----
    # worth 越大越值得长期记住。≥ memory_keep → 直接生效；[memory_pending, memory_keep) → 待确认区；更低丢弃。
    memory_keep: float = 0.70
    memory_pending: float = 0.40
    # ---- 工具门控（架构 3.3d）----
    # appropriate = JEV 对"这次调用必要且参数符合用户意图"的 Noul 值，不是成功率。
    # write_local：appropriate ≥ gate_write → 免确认执行；否则问用户。
    gate_write: float = 0.80
    # external：一律问用户；appropriate < gate_external_deny → 直接拒绝，不打扰用户。
    gate_external_deny: float = 0.50
    # ---- 模型路由 ----
    # P(hard) ≥ route_cloud → 升级到 step-5；越小越容易上云。
    route_cloud: float = 0.50
    # 需要写代码的 Noul ≥ route_code 且 P(simple) < route_code_simple_max → 也升级。
    route_code: float = 0.80
    route_code_simple_max: float = 0.30
    # ---- 上下文压缩（架构第 8 节）----
    # 估算 token > context_budget × compress_high → 触发压缩；压到 context_budget × compress_target 以下为止。
    context_budget: int = 24000
    compress_high: float = 0.70
    compress_target: float = 0.45
    keep_recent_turns: int = 2         # 最近几轮（含当前轮）原样保留
    keep_recent_tool_results: int = 4  # 最近几条工具结果不做截短
    # ---- 轮内升级 ----
    # 本地模型连续给出几次非法工具参数就升级到云端
    malformed_before_escalate: int = 2


@dataclass
class Config:
    local: Endpoint
    backup: Endpoint
    cloud: Endpoint
    jev_url: str
    jev_model: str
    jev_use_proxy: bool
    linear_use_proxy: bool
    linear_team_key: str
    linear_project_name: str
    data_dir: Path
    skills_dir: Path
    vault_dir: Path
    workspace: Path
    thresholds: Thresholds = field(default_factory=Thresholds)
    max_steps: int = 16
    tool_result_chars: int = 6000
    shell_allow: tuple[str, ...] = (
        "python -m pytest",
        "python -m unittest",
        "python -m tinyledger",
        "python -m py_compile",
        "pytest",
    )
    memory_extract: bool = True

    @property
    def jev_key(self) -> str:
        return os.environ.get("TYPESAFE_API_KEY", "")

    @property
    def linear_key(self) -> str:
        return os.environ.get("LINEAR_API_KEY", "")

    @classmethod
    def load(cls, workspace: str | Path | None = None) -> "Config":
        load_dotenv()
        data_dir = Path(_env("AGENT_DATA_DIR", str(ROOT / "var")))
        ws = Path(workspace) if workspace else Path(_env("AGENT_WORKSPACE", str(data_dir / "workspace" / "tinyledger")))
        return cls(
            local=Endpoint(
                name="local",
                base_url=_env("AGENT_LOCAL_BASE", "http://127.0.0.1:8000/v1"),
                model=_env("AGENT_LOCAL_MODEL", "nemotron"),
                max_concurrency=8,
            ),
            backup=Endpoint(
                name="backup",
                base_url=_env("AGENT_BACKUP_BASE", "http://127.0.0.1:11434/v1"),
                model=_env("AGENT_BACKUP_MODEL", "qwen3.8:27b"),
                max_concurrency=2,
                extra={"reasoning_effort": "none"},
            ),
            cloud=Endpoint(
                name="cloud",
                base_url=_env("AGENT_CLOUD_BASE", "https://api.stepfun.com/step_plan/v1"),
                model=_env("AGENT_CLOUD_MODEL", "step-5-preview"),
                api_key_env="STEPFUN_API_KEY",
                use_proxy=_flag("AGENT_CLOUD_PROXY", False),  # StepFun 在国内，节点可直连
                # 2026-09-24 实测并发约 8 个就开始 429，留一半余量
                max_concurrency=4,
            ),
            jev_url=_env("AGENT_JEV_URL", "https://api.typesafe.ai/v1/systemone"),
            jev_model=_env("AGENT_JEV_MODEL", "jev-latest"),
            jev_use_proxy=_flag("AGENT_JEV_PROXY", True),
            linear_use_proxy=_flag("AGENT_LINEAR_PROXY", True),
            linear_team_key=_env("LINEAR_TEAM_KEY", "DAY"),
            linear_project_name=_env("LINEAR_PROJECT_NAME", "DGX-Spark Agent 演示"),
            data_dir=data_dir,
            skills_dir=Path(_env("AGENT_SKILLS_DIR", str(ROOT / "skills"))),
            vault_dir=Path(_env("AGENT_VAULT", str(ROOT / "demo" / "obsidian-vault"))),
            workspace=ws,
            memory_extract=_flag("AGENT_MEMORY_EXTRACT", True),
        )
