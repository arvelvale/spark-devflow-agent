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
    no_think: dict = field(default_factory=dict)  # 关闭思考时额外合并的字段（辅助任务用）
    max_tokens: int = 4096        # 主循环单次输出上限（推理 token 也算在内）
    api_key_value: str = ""       # 面板「模型设置」里填的 Key；非空时优先于 api_key_env
    # 私有 = 部署在自己控制的机器上。只有私有模型能看到隐私记忆、跑摘要和记忆抽取。
    # None = 按分工位推断：local / backup 私有，cloud 不私有（与改造前"云端轮次过滤隐私"的行为一致）
    private: bool | None = None
    provider: str = ""            # 来自哪个供应商（models.json 的 id），状态展示用

    @property
    def api_key(self) -> str:
        if self.api_key_value:
            return self.api_key_value
        return os.environ.get(self.api_key_env, "") if self.api_key_env else ""

    @property
    def needs_key(self) -> bool:
        return bool(self.api_key_env or self.api_key_value)

    @property
    def configured(self) -> bool:
        return not self.needs_key or bool(self.api_key)

    @property
    def is_private(self) -> bool:
        return self.private if self.private is not None else self.name in ("local", "backup")


@dataclass
class Thresholds:
    # ---- 技能选择（架构 3.3a）----
    # gate = 三个门控 Noul 的均值，越大越说明"这句话需要技能"。gate < skill_gate → 不推荐任何技能。
    skill_gate: float = 0.30
    # 第一级 Choice 里 P(none) ≥ skill_none → 不用技能（JEV 已明确判断没有技能适用，不再进第二级）。
    skill_none: float = 0.50
    # 第二级每个候选一个 fits Noul，越大越合适。最高 fits < skill_fit → 全部拒绝。
    skill_fit: float = 0.30
    # 其余候选 fits ≥ skill_multi → 作为附加技能一起加载（组合技能）。
    # 2026-09-24 按任务集 v1 标定：组合任务的第二技能 fits 0.52–0.63，单技能任务的第二名 0.07；0.70 会漏掉全部组合
    skill_multi: float = 0.50
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
    # 两个 JEV Noul 一次问完（2026-09-24 用 eval/gate_cases.json 实测选定，单问题分不开合法/越界）：
    #   in_scope   = "这次调用是不是完成请求的合理步骤"，越大越放心
    #   collateral = "会不会删改与请求无关的内容"，越大越危险
    # write_local：collateral ≥ gate_collateral → 问用户；否则 in_scope ≥ gate_write → 免确认执行；否则问用户。
    gate_write: float = 0.50
    gate_collateral: float = 0.50
    # external：一律问用户；in_scope < gate_external_deny → 直接拒绝，不打扰用户。
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
    # 阶段 A（逐调用裁剪，参考 fast-jev-compaction）：JEV 对每个旧工具调用问两题，都是"还需要吗"，越大越该留。
    #   keep_result ≥ compress_keep → 调用和结果原样保留
    #   否则 keep_call ≥ compress_keep → 保留调用，结果截成开头 + 归档编号
    #   否则 → 调用和结果一起移除（原文进归档，可 read_archive 取回）
    compress_keep: float = 0.50
    compress_state_tokens: int = 12000  # 发给 JEV 的整段对话视图估算上限（JEV 单请求约 32k）
    compress_min_result: int = 200     # 结果短于这个字数的调用不值得问，直接留着
    # 判过"保留"的调用，之后又新增多少次工具调用（上下文确实变了）才重新问。越小越勤快、JEV 开销越大。
    # 2026-09-26 实测：不设这个时 19 步触发 18 次压缩、只有 2 次真删了东西，JEV 白花 5.7 万 token
    compress_rejudge_after: int = 6
    # 防抖：一次压缩之后，上下文至少再涨 context_budget × compress_cooldown 才会再压。越大越少压、越不抖。
    # 2026-09-26 实测：每步都压时，刚重读回来的文件下一步又被截掉，模型反复重读直到撞步数上限
    compress_cooldown: float = 0.15
    # ---- 跑偏提醒 ----
    # 写操作连续被 JEV 判为"不像这个请求需要的步骤"（in_scope 低于门控阈值）多少次，就提醒模型回到计划或收尾。
    # 设计值 3 → 第 3、6、9… 次各提醒一次；中间只要有一次写操作被判为合理步骤，计数清零。
    # 来由（2026-09-26 节点实测）：修完 DAY-298 后模型又绕了 16 步手工验证，门控每一步都判了"不像"，
    # 但 --yes 下全部放行，这个信号被浪费了。
    drift_streak: int = 3
    # ---- 轮内升级 ----
    # 本地模型连续给出几次非法工具参数就升级到云端
    malformed_before_escalate: int = 2


@dataclass
class Config:
    local: Endpoint     # 分工位「主力」
    backup: Endpoint    # 分工位「备用」
    cloud: Endpoint     # 分工位「难题」
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
    max_steps: int = 30   # 2026-09-24 实测：修一个 bug 用满 16 步还差最后汇报
    tool_result_chars: int = 6000
    shell_allow: tuple[str, ...] = (
        "python -m pytest",
        "python -m unittest",
        "python -m tinyledger",
        "python -m py_compile",
        "pytest",
    )
    memory_extract: bool = True
    local_thinking: bool = True   # 本地主模型在主循环里是否开思考；辅助任务一律关
    asr: Endpoint | None = None   # 语音识别（阶跃），和「难题」分工位解耦：换了难题模型语音输入照常可用

    @property
    def jev_key(self) -> str:
        return os.environ.get("TYPESAFE_API_KEY", "")

    @property
    def linear_key(self) -> str:
        return os.environ.get("LINEAR_API_KEY", "")

    @property
    def models_path(self) -> Path:
        return self.data_dir / "models.json"

    @classmethod
    def load(cls, workspace: str | Path | None = None) -> "Config":
        load_dotenv()
        th = Thresholds()
        th.context_budget = int(_env("AGENT_CONTEXT_BUDGET", str(th.context_budget)))
        data_dir = Path(_env("AGENT_DATA_DIR", str(ROOT / "var")))
        ws = Path(workspace) if workspace else Path(_env("AGENT_WORKSPACE", str(data_dir / "workspace" / "tinyledger")))
        cfg = cls(
            local=Endpoint(
                name="local",
                base_url=_env("AGENT_LOCAL_BASE", "http://127.0.0.1:8000/v1"),
                model=_env("AGENT_LOCAL_MODEL", "nemotron"),
                max_concurrency=8,
                # Nemotron 默认开思考；模型 README 的官方关法
                no_think={"chat_template_kwargs": {"enable_thinking": False}},
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
                # 2026-09-24 实测：修 bug 一步就用满 4096 被截断（推理很长），放宽
                max_tokens=16384,
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
            thresholds=th,
            memory_extract=_flag("AGENT_MEMORY_EXTRACT", True),
            local_thinking=_flag("AGENT_LOCAL_THINKING", True),
        )
        cfg.asr = Endpoint("asr", cfg.cloud.base_url, "", api_key_env="STEPFUN_API_KEY", use_proxy=cfg.cloud.use_proxy)
        # 面板里保存过模型设置（var/models.json）就以它为准；没有则沿用上面的默认值和环境变量
        from .models import ModelStore
        ModelStore(cfg.models_path).apply(cfg)
        return cfg
