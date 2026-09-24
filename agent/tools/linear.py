"""Linear 工具（GraphQL）。

安全边界：所有读写都限定在配置的演示项目内（默认「DGX-Spark Agent 演示」），
按编号访问项目外的 issue 一律拒绝，防止 agent 碰到同一工作区里的真实项目。
团队和项目按名字在运行时解析，仓库里不写任何工作区 ID。
"""
from __future__ import annotations

import threading

from ..http import HttpError, post_json
from .base import Permission, Tool, ToolContext, ToolError, arg, params

API = "https://api.linear.app/graphql"


class LinearClient:
    def __init__(self, api_key: str, team_key: str, project_name: str, *, use_proxy: bool = True):
        self.api_key = api_key
        self.team_key = team_key
        self.project_name = project_name
        self.use_proxy = use_proxy
        self._lock = threading.Lock()
        self._team: dict | None = None
        self._project_id: str | None = None

    def gql(self, query: str, variables: dict | None = None) -> dict:
        if not self.api_key:
            raise ToolError("未配置 LINEAR_API_KEY")
        try:
            data, _ = post_json(API, {"query": query, "variables": variables or {}},
                                {"Authorization": self.api_key}, timeout=30, use_proxy=self.use_proxy, retries=2)
        except HttpError as exc:
            raise ToolError(f"Linear 请求失败：{exc}")
        if data.get("errors"):
            raise ToolError("Linear 返回错误：" + "; ".join(e.get("message", "") for e in data["errors"])[:300])
        return data["data"]

    def _resolve(self) -> None:
        with self._lock:
            if self._team and self._project_id:
                return
            d = self.gql(
                "query($k:String!,$p:String!){teams(filter:{key:{eq:$k}}){nodes{id name states{nodes{id name type}}}}"
                " projects(filter:{name:{eq:$p}}){nodes{id name}}}",
                {"k": self.team_key, "p": self.project_name},
            )
            teams, projects = d["teams"]["nodes"], d["projects"]["nodes"]
            if not teams:
                raise ToolError(f"找不到团队 {self.team_key}")
            if not projects:
                raise ToolError(f"找不到项目「{self.project_name}」")
            self._team, self._project_id = teams[0], projects[0]["id"]

    @property
    def team(self) -> dict:
        self._resolve()
        return self._team  # type: ignore[return-value]

    @property
    def project_id(self) -> str:
        self._resolve()
        return self._project_id  # type: ignore[return-value]

    def issue(self, identifier: str) -> dict:
        d = self.gql(
            "query($id:String!){issue(id:$id){id identifier title description url priority "
            "state{name} project{id} labels{nodes{name}} assignee{name} parent{identifier title} "
            "children{nodes{identifier title state{name}}} comments(first:10){nodes{body createdAt user{name}}}}}",
            {"id": identifier},
        )
        issue = d.get("issue")
        if not issue:
            raise ToolError(f"找不到 issue {identifier}")
        if (issue.get("project") or {}).get("id") != self.project_id:
            raise ToolError(f"{identifier} 不属于演示项目「{self.project_name}」，拒绝访问")
        return issue

    def state_id(self, name: str) -> str:
        states = self.team["states"]["nodes"]
        for s in states:
            if s["name"].lower() == name.lower() or s["type"].lower() == name.lower():
                return s["id"]
        raise ToolError(f"没有叫「{name}」的状态。可选：" + " / ".join(s["name"] for s in states))


def _client(ctx: ToolContext) -> LinearClient:
    if ctx.linear is None:
        raise ToolError("Linear 未配置")
    return ctx.linear


def _fmt_issue_line(i: dict) -> str:
    parent = f"  ↳ 父任务 {i['parent']['identifier']}" if i.get("parent") else ""
    return f"{i['identifier']} [{i['state']['name']}] P{i.get('priority', 0)} {i['title']}{parent}"


def linear_list_issues(args: dict, ctx: ToolContext) -> str:
    lc = _client(ctx)
    flt: dict = {"project": {"id": {"eq": lc.project_id}}}
    state = arg(args, "state")
    if state:
        flt["state"] = {"name": {"eqIgnoreCase": state}}
    n = min(int(arg(args, "limit", 30)), 100)
    d = lc.gql("query($f:IssueFilter,$n:Int){issues(filter:$f,first:$n,orderBy:updatedAt)"
               "{nodes{identifier title priority state{name} parent{identifier}}}}", {"f": flt, "n": n})
    nodes = d["issues"]["nodes"]
    return "\n".join(_fmt_issue_line(i) for i in nodes) or "项目里没有 issue"


def linear_get_issue(args: dict, ctx: ToolContext) -> str:
    i = _client(ctx).issue(arg(args, "identifier", required=True))
    parts = [f"{i['identifier']} {i['title']}", f"状态：{i['state']['name']}  优先级：P{i.get('priority', 0)}  链接：{i['url']}"]
    if i.get("labels", {}).get("nodes"):
        parts.append("标签：" + "、".join(l["name"] for l in i["labels"]["nodes"]))
    if i.get("parent"):
        parts.append(f"父任务：{i['parent']['identifier']} {i['parent']['title']}")
    parts.append("描述：\n" + (i.get("description") or "（无）"))
    kids = i.get("children", {}).get("nodes") or []
    if kids:
        parts.append("子任务：\n" + "\n".join(f"- {c['identifier']} [{c['state']['name']}] {c['title']}" for c in kids))
    comments = i.get("comments", {}).get("nodes") or []
    if comments:
        parts.append("评论：\n" + "\n".join(f"- {c['user']['name'] if c.get('user') else '?'}：{c['body'][:300]}"
                                        for c in comments))
    return "\n".join(parts)


def linear_create_issue(args: dict, ctx: ToolContext) -> str:
    lc = _client(ctx)
    inp: dict = {
        "teamId": lc.team["id"],
        "projectId": lc.project_id,
        "title": arg(args, "title", required=True),
        "description": arg(args, "description", ""),
    }
    parent = arg(args, "parent")
    if parent:
        inp["parentId"] = lc.issue(parent)["id"]
    priority = arg(args, "priority")
    if priority is not None:
        inp["priority"] = int(priority)
    d = lc.gql("mutation($i:IssueCreateInput!){issueCreate(input:$i){success issue{identifier url}}}", {"i": inp})
    issue = d["issueCreate"]["issue"]
    return f"已创建 {issue['identifier']}：{inp['title']}（{issue['url']}）"


def linear_update_issue(args: dict, ctx: ToolContext) -> str:
    lc = _client(ctx)
    issue = lc.issue(arg(args, "identifier", required=True))
    done = []
    state = arg(args, "state")
    if state:
        lc.gql("mutation($id:String!,$s:String!){issueUpdate(id:$id,input:{stateId:$s}){success}}",
               {"id": issue["id"], "s": lc.state_id(state)})
        done.append(f"状态 → {state}")
    comment = arg(args, "comment")
    if comment:
        lc.gql("mutation($id:String!,$b:String!){commentCreate(input:{issueId:$id,body:$b}){success}}",
               {"id": issue["id"], "b": comment})
        done.append("已添加评论")
    if not done:
        raise ToolError("state 和 comment 至少填一个")
    return f"{issue['identifier']}：" + "；".join(done)


TOOLS = [
    Tool("linear_list_issues", "列出演示项目里的 Linear issue（编号、状态、优先级、标题）。",
         params({"state": {"type": "string", "description": "按状态名过滤，如 Todo / In Progress / Done"},
                 "limit": {"type": "integer", "description": "默认 30"}}),
         Permission.READ, linear_list_issues),
    Tool("linear_get_issue", "读取一个 Linear issue 的详情（描述、子任务、评论）。",
         params({"identifier": {"type": "string", "description": "如 DAY-12"}}, ["identifier"]),
         Permission.READ, linear_get_issue),
    Tool("linear_create_issue", "在演示项目里创建 issue；填 parent 则作为子任务。外部可见，执行前会请用户确认。",
         params({"title": {"type": "string"}, "description": {"type": "string", "description": "Markdown，含验收标准"},
                 "parent": {"type": "string", "description": "父 issue 编号"},
                 "priority": {"type": "integer", "description": "0 无 / 1 紧急 / 2 高 / 3 中 / 4 低"}}, ["title"]),
         Permission.EXTERNAL, linear_create_issue),
    Tool("linear_update_issue", "更新演示项目里的 issue：改状态、加评论。外部可见，执行前会请用户确认。",
         params({"identifier": {"type": "string"}, "state": {"type": "string"}, "comment": {"type": "string"}},
                ["identifier"]),
         Permission.EXTERNAL, linear_update_issue),
]
