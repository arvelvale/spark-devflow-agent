"""在 Linear 演示项目里创建演示 issue（按标题幂等，重复运行不会重复创建）。

  python demo/seed/seed_linear.py            # 创建缺少的演示 issue
  python demo/seed/seed_linear.py --reset    # 先归档项目里的全部 issue 再重建（录视频前用）

只操作 LINEAR_PROJECT_NAME 指定的演示项目（默认「DGX-Spark Agent 演示」）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent.config import Config  # noqa: E402
from agent.tools.linear import LinearClient  # noqa: E402

ISSUES = [
    {
        "title": "金额累加精度错误：三笔 0.1 合计显示 0.30000000000000004",
        "priority": 2,
        "description": "来源：2026-09-23 周会。\n\n`tinyledger list` 的合计用 float 累加，出现浮点误差。\n\n"
                       "决定：金额统一按\"分\"存整数，读取老数据时自动换算。优先级高于月度汇总。\n\n"
                       "验收：\n- 新增测试：三笔 0.1 相加等于 0.3\n- 老的 ledger.json（float 金额）仍能正确读取\n"
                       "- `python -m unittest` 全部通过",
    },
    {
        "title": "CSV 导出：tinyledger export --month --out",
        "priority": 3,
        "description": "来源：2026-09-21 需求评审。\n\n`tinyledger export --month 2026-09 --out sep.csv`，"
                       "列为 日期/分类/金额/备注。编码 UTF-8 带 BOM（否则 Excel 打开中文乱码）。\n\n"
                       "未定：是否支持日期区间 --from/--to（先不做）。",
    },
    {
        "title": "月度汇总：tinyledger summary --month",
        "priority": 3,
        "description": "来源：2026-09-21 需求评审。\n\n按分类汇总当月金额，按金额降序，最后一行合计。终端表格即可，不做图表。\n\n"
                       "依赖：金额精度修复完成后再做。",
    },
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true")
    args = p.parse_args()
    cfg = Config.load()
    if not cfg.linear_key:
        sys.exit("未配置 LINEAR_API_KEY")
    lc = LinearClient(cfg.linear_key, cfg.linear_team_key, cfg.linear_project_name, use_proxy=cfg.linear_use_proxy)
    existing = lc.gql("query($p:ID!){issues(filter:{project:{id:{eq:$p}}},first:100){nodes{id identifier title}}}",
                      {"p": lc.project_id})["issues"]["nodes"]
    if args.reset:
        for i in existing:
            lc.gql("mutation($id:String!){issueArchive(id:$id){success}}", {"id": i["id"]})
            print(f"已归档 {i['identifier']} {i['title']}")
        existing = []
    titles = {i["title"] for i in existing}
    for spec in ISSUES:
        if spec["title"] in titles:
            print(f"已存在，跳过：{spec['title']}")
            continue
        d = lc.gql("mutation($i:IssueCreateInput!){issueCreate(input:$i){issue{identifier url}}}", {"i": {
            "teamId": lc.team["id"], "projectId": lc.project_id, **spec}})
        issue = d["issueCreate"]["issue"]
        print(f"已创建 {issue['identifier']} {spec['title']}")


if __name__ == "__main__":
    main()
