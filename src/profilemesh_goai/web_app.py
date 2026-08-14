"""Minimal management-side web entry for an OrgSight AgentTeams request."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import uvicorn
from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MAX_REQUEST_LENGTH = 2_000
POLL_INTERVAL_SECONDS = 2
RESULT_TIMEOUT_SECONDS = 15 * 60
REGISTRY_PATH = REPOSITORY_ROOT / "agent-specs" / "registry.yaml"
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "orgsight-logo.svg"


def load_local_environment() -> None:
    load_dotenv(REPOSITORY_ROOT / ".env", override=False)


class MatrixError(RuntimeError):
    """A user-safe Matrix transport failure."""


class AgentTeamsCasesError(RuntimeError):
    """A user-safe failure while reading AgentTeams case data."""


def _agentteams_cases_base_url() -> str:
    load_local_environment()
    base_url = os.environ.get("AGENTTEAMS_CONTROLLER_URL", "http://127.0.0.1:28080").strip().rstrip("/")
    if not base_url:
        raise AgentTeamsCasesError("未配置 AgentTeams Controller 地址")
    return base_url


def _read_agentteams_json(path: str) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    token = os.environ.get("AGENTTEAMS_AUTH_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{_agentteams_cases_base_url()}{path}", headers=headers, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read()
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise AgentTeamsCasesError(f"AgentTeams 案例接口失败（HTTP {error.code}）：{detail}") from error
    except URLError as error:
        raise AgentTeamsCasesError("无法连接 AgentTeams Controller 案例接口") from error
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError as error:
        raise AgentTeamsCasesError("AgentTeams 案例接口返回了无法解析的响应") from error
    if not isinstance(payload, dict):
        raise AgentTeamsCasesError("AgentTeams 案例接口返回格式错误")
    return payload


def agentteams_cases() -> dict[str, Any]:
    """Read the live completed-case index from AgentTeams."""
    return _read_agentteams_json("/api/v1/cases")


def agentteams_case(case_id: str) -> dict[str, Any]:
    """Read one live completed case from AgentTeams."""
    if not case_id or "/" in case_id or "\\" in case_id or case_id in {".", ".."}:
        raise AgentTeamsCasesError("案例标识无效")
    return _read_agentteams_json(f"/api/v1/cases/{quote(case_id, safe='')}")


def configured_leaders() -> list[dict[str, str]]:
    """Read selectable teams and Leaders from the repository registry."""

    leaders: list[dict[str, str]] = []
    team_name = ""
    display_name = ""
    for raw_line in REGISTRY_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("- name:"):
            team_name = line.split(":", 1)[1].strip()
            display_name = ""
        elif line.startswith("display_name:") and team_name:
            display_name = line.split(":", 1)[1].strip()
        elif line.startswith("leader:") and team_name and display_name:
            leader = line.split(":", 1)[1].strip()
            leaders.append({"team": team_name, "display_name": display_name, "leader": leader})
            team_name = ""
            display_name = ""
    if not leaders:
        raise MatrixError("未在 Agent 注册表中找到可用 Team Leader")
    return leaders


def leader_matrix_id(leader: str) -> str:
    load_local_environment()
    domain = os.environ.get("AGENTTEAMS_MATRIX_DOMAIN", "").strip()
    if not domain:
        manager_id = os.environ.get("PROFILEMESH_MANAGER_MATRIX_ID", "").strip()
        if ":" in manager_id:
            domain = manager_id.split(":", 1)[1]
    if not domain:
        raise MatrixError("未配置 AgentTeams Matrix 域名")
    return f"@{leader}:{domain}"


class MatrixClient:
    """Small Matrix wrapper used only by the management-side request page."""

    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.token: str | None = None

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        payload: bytes | None = None
        if body is not None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(f"{self.base_url}{path}", data=payload, headers=headers, method=method)
        try:
            with urlopen(request, timeout=15) as response:
                raw = response.read()
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise MatrixError(f"Matrix 请求失败（HTTP {error.code}）：{detail}") from error
        except URLError as error:
            raise MatrixError("无法连接本机 AgentTeams Matrix 服务") from error
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError as error:
            raise MatrixError("Matrix 返回了无法解析的响应") from error

    def login(self) -> None:
        response = self._request("POST", "/_matrix/client/v3/login", {
            "type": "m.login.password",
            "identifier": {"type": "m.id.user", "user": self.username},
            "password": self.password,
        })
        token = response.get("access_token")
        if not isinstance(token, str) or not token:
            raise MatrixError("网页请求账号登录失败：Matrix 未返回访问令牌")
        self.token = token

    def create_source_room(self, request_id: str, leader_id: str) -> str:
        response = self._request("POST", "/_matrix/client/v3/createRoom", {
            "name": f"OrgSight 请求 {request_id[:8]}",
            "preset": "private_chat",
            "is_direct": True,
            "invite": [leader_id],
        })
        room_id = response.get("room_id")
        if not isinstance(room_id, str) or not room_id:
            raise MatrixError("创建请求房间失败：未返回 room_id")
        return room_id

    def send_message(self, room_id: str, text: str, transaction_id: str, mentioned_user_id: str) -> None:
        encoded_room = quote(room_id, safe="")
        encoded_transaction = quote(transaction_id, safe="")
        self._request(
            "PUT",
            f"/_matrix/client/v3/rooms/{encoded_room}/send/m.room.message/{encoded_transaction}",
            {"msgtype": "m.text", "body": text, "m.mentions": {"user_ids": [mentioned_user_id]}},
        )


@dataclass
class AnalysisRequest:
    request_id: str
    prompt: str
    leader: str
    status: str = "queued"
    room_id: str | None = None
    result_markdown: str | None = None
    case_id: str | None = None
    error: str | None = None


class RequestStore:
    def __init__(self) -> None:
        self._items: dict[str, AnalysisRequest] = {}
        self._lock = threading.Lock()

    def create(self, prompt: str, leader: str) -> AnalysisRequest:
        item = AnalysisRequest(request_id=uuid.uuid4().hex, prompt=prompt, leader=leader)
        with self._lock:
            self._items[item.request_id] = item
        return item

    def get(self, request_id: str) -> AnalysisRequest | None:
        with self._lock:
            return self._items.get(request_id)

    def update(self, request_id: str, **changes: Any) -> None:
        with self._lock:
            item = self._items[request_id]
            for key, value in changes.items():
                setattr(item, key, value)


STORE = RequestStore()


def configured_matrix_client() -> MatrixClient:
    load_local_environment()
    values = {
        "AGENTTEAMS_MATRIX_URL": os.environ.get("AGENTTEAMS_MATRIX_URL", "").strip(),
        "PROFILEMESH_WEB_MATRIX_USER": os.environ.get("PROFILEMESH_WEB_MATRIX_USER", "").strip(),
        "PROFILEMESH_WEB_MATRIX_PASSWORD": os.environ.get("PROFILEMESH_WEB_MATRIX_PASSWORD", "").strip(),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise MatrixError("网页尚未配置：请在 .env 填写 " + "、".join(missing))
    return MatrixClient(
        values["AGENTTEAMS_MATRIX_URL"], values["PROFILEMESH_WEB_MATRIX_USER"],
        values["PROFILEMESH_WEB_MATRIX_PASSWORD"],
    )


def completed_case_for_room(room_id: str, known_case_ids: set[str]) -> dict[str, Any] | None:
    expected = {room_id, f"matrix:{room_id}"}
    summaries = agentteams_cases().get("cases", [])
    if not isinstance(summaries, list):
        raise AgentTeamsCasesError("AgentTeams 案例列表格式错误")
    new_cases: list[dict[str, Any]] = []
    for summary in summaries:
        if not isinstance(summary, dict) or summary.get("case_id") in known_case_ids:
            continue
        new_cases.append(summary)
        if summary.get("source_room_id") in expected:
            return agentteams_case(str(summary["case_id"]))
    # Compatibility with the currently running Controller version, whose
    # case summary predates source_room_id. The page submits one request at a
    # time, so one and only one newly submitted task is unambiguous.
    if len(new_cases) == 1:
        return agentteams_case(str(new_cases[0]["case_id"]))
    return None


def execute_request(request_id: str) -> None:
    item = STORE.get(request_id)
    if item is None:
        return
    try:
        client = configured_matrix_client()
        leader_id = leader_matrix_id(item.leader)
        known_case_ids = {
            str(case.get("case_id")) for case in agentteams_cases().get("cases", [])
            if isinstance(case, dict) and case.get("case_id")
        }
        STORE.update(request_id, status="creating_source_room")
        client.login()
        room_id = client.create_source_room(request_id, leader_id)
        STORE.update(request_id, status="waiting_for_leader", room_id=room_id)
        client.send_message(room_id, f"{leader_id} {item.prompt}", f"profilemesh-{request_id}", leader_id)
        STORE.update(request_id, status="processing")
        deadline = time.monotonic() + RESULT_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            completed = completed_case_for_room(room_id, known_case_ids)
            if completed:
                STORE.update(
                    request_id, status="completed", case_id=completed.get("case_id"),
                    result_markdown=completed.get("result_markdown"),
                )
                return
            time.sleep(POLL_INTERVAL_SECONDS)
        STORE.update(request_id, status="timed_out", error="等待 AgentTeams 最终结果超时；任务仍可能继续运行。")
    except (MatrixError, AgentTeamsCasesError) as error:
        STORE.update(request_id, status="failed", error=str(error))
    except Exception:
        STORE.update(request_id, status="failed", error="网页请求处理失败；请查看本机服务日志。")


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OrgSight</title><style>
:root{color-scheme:dark;--bg:#0d0f10;--sidebar:#151719;--panel:#1b1e20;--panel-strong:#24282b;--line:#303438;--text:#f4f5f6;--muted:#92999f;--accent:#e8732a;--accent-soft:#e8732a18;--accent-hover:#f07f38;--sidebar-width:clamp(16rem,22vw,22rem)}*{box-sizing:border-box}html,body{min-width:0}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}.shell{min-height:100vh;min-width:0;display:grid;grid-template-columns:var(--sidebar-width) minmax(0,1fr)}.sidebar{position:fixed;inset:0 auto 0 0;width:var(--sidebar-width);overflow:auto;background:var(--sidebar);border-right:1px solid #2b2f32;display:flex;flex-direction:column;padding:20px 14px}.brand{display:flex;align-items:center;gap:11px;padding:0 8px 22px;font-size:18px;font-weight:680;letter-spacing:-.15px}.mark{display:grid;place-items:center;width:30px;height:30px;border-radius:9px;color:#171717;background:#f3f4f4;font-size:12px;font-weight:800}.new-analysis{width:100%;border:1px solid #303438;border-radius:12px;background:var(--panel-strong);color:var(--text);padding:12px 14px;text-align:left;font:inherit;font-weight:620;cursor:pointer;transition:.16s ease}.new-analysis:hover{border-color:#444a4f;background:#2a2e31}.new-analysis span{color:#c8cdd3;font-size:19px;vertical-align:-1px;margin-right:9px}.side-label{margin:30px 9px 9px;color:#7f878e;font-size:12px;font-weight:650;letter-spacing:.04em}.case-list{display:grid;gap:4px;min-width:0}.case-button{width:100%;min-width:0;border:1px solid transparent;border-radius:10px;background:transparent;color:var(--text);padding:10px 11px;text-align:left;font:inherit;cursor:pointer}.case-button:hover,.case-button.active{border-color:#2c3033;background:#202326}.case-title{display:block;width:100%;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:560}.case-meta{display:block;margin-top:2px;color:var(--muted);font-size:12px}.workspace{grid-column:2;min-width:0;display:flex;min-height:100vh;flex-direction:column}.topbar{height:70px;display:flex;align-items:center;padding:0 42px}.top-title{font-weight:680;font-size:18px;letter-spacing:-.2px}.main{width:100%;max-width:1000px;min-width:0;margin:0 auto;padding:42px 42px 76px;flex:1;display:flex;flex-direction:column}.composer-view{width:min(780px,100%);margin:auto;transform:translateY(-4vh)}.welcome{font-size:34px;line-height:1.22;letter-spacing:-.65px;margin:0 0 30px}.composer{border:1px solid #363b3f;background:var(--panel);border-radius:17px;padding:17px 17px 13px;box-shadow:0 18px 48px #0000002e}.composer textarea{display:block;width:100%;height:auto;min-height:52px;max-height:240px;overflow-y:hidden;scrollbar-width:thin;scrollbar-color:#60676d transparent;resize:none;border:0;outline:0;background:transparent;color:var(--text);font:inherit;font-size:16px;line-height:1.65;padding:0 7px 14px 1px}.composer textarea::-webkit-scrollbar{width:7px}.composer textarea::-webkit-scrollbar-track{background:transparent}.composer textarea::-webkit-scrollbar-thumb{border:2px solid transparent;border-radius:999px;background:#60676d;background-clip:padding-box}.composer textarea::-webkit-scrollbar-thumb:hover{background:#7a8288;background-clip:padding-box}.composer textarea::placeholder{color:#777f86}.composer-bottom{display:flex;align-items:center;justify-content:space-between;gap:12px}.team-picker{position:relative;min-width:0}.team-trigger{max-width:270px;display:flex;align-items:center;gap:7px;border:1px solid #363b3f;border-radius:10px;background:#292d30;color:#e3e6e8;padding:9px 12px;font:inherit;font-size:13px;font-weight:620;cursor:pointer}.team-trigger:hover,.team-trigger[aria-expanded="true"]{border-color:#4b5156;background:#303438}.team-trigger-label{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.team-chevron{flex:0 0 auto;width:14px;height:14px;margin-left:3px;color:#969da3;transition:transform .16s ease}.team-trigger[aria-expanded="true"] .team-chevron{transform:rotate(180deg)}.team-menu{position:absolute;left:0;top:calc(100% + 8px);z-index:5;width:260px;padding:6px;border:1px solid #383d41;border-radius:12px;background:#24282b;box-shadow:0 16px 36px #0008}.team-menu button{width:100%;display:flex;align-items:center;gap:10px;border:0;border-radius:8px;background:transparent;color:#d7dbde;padding:10px 11px;text-align:left;font:inherit;font-size:13px;cursor:pointer}.team-menu button:hover,.team-menu button.active{background:#31363a;color:white}.team-menu-dot{width:7px;height:7px;border-radius:50%;background:#666e74}.team-menu button.active .team-menu-dot{background:var(--accent)}.submit{border:0;border-radius:10px;min-width:96px;padding:10px 17px;background:var(--accent);color:white;font:inherit;font-weight:680;cursor:pointer;transition:.16s ease}.submit:hover{background:var(--accent-hover)}.submit:disabled{opacity:.55;cursor:wait}.status{min-height:23px;margin-top:14px;color:#bbc1c7;font-size:13px}.status.error{color:#ffaaa3}.case-view{width:100%;min-width:0;max-width:800px;margin:18px auto 0}.case-kicker{color:var(--muted);font-size:13px;margin-bottom:7px}.case-heading{margin:0;overflow-wrap:anywhere;font-size:28px;letter-spacing:-.35px}.case-question{min-width:0;margin:23px 0 16px;padding:15px 17px;border-left:3px solid var(--accent);border-radius:0 10px 10px 0;background:var(--panel);color:#d5d9de}.section-label{font-size:12px;color:var(--muted);font-weight:650;margin-bottom:7px}.request-copy{overflow-wrap:anywhere;white-space:pre-wrap}.result{min-width:0;overflow-wrap:anywhere;padding:22px;border:1px solid var(--line);border-radius:14px;background:#181b1d;color:#e6e9ec;font-size:15px;line-height:1.75}.result h1,.result h2,.result h3{overflow-wrap:anywhere;line-height:1.35;margin:1.55em 0 .55em}.result h1{font-size:24px;margin-top:0}.result h2{font-size:20px}.result h3{font-size:17px}.result p{margin:.65em 0}.result ul,.result ol{padding-left:1.45em}.result li{margin:.35em 0}.result hr{border:0;border-top:1px solid var(--line);margin:1.5em 0}.result code{overflow-wrap:anywhere;padding:.12em .35em;border-radius:4px;background:#2a2e32;font:13px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}.result table{width:100%;max-width:100%;table-layout:fixed;border-collapse:collapse;margin:1em 0;font-size:14px}.result th,.result td{overflow-wrap:anywhere;word-break:break-word;border:1px solid var(--line);padding:9px 10px;vertical-align:top;text-align:left}.result th{background:#292d31}.hidden{display:none!important}@media(max-width:760px){.shell{grid-template-columns:1fr}.sidebar{display:none}.workspace{grid-column:1}.topbar{padding:0 20px}.main{padding:25px 20px}.composer-view{transform:none;margin:60px auto}.welcome{font-size:29px}.team-trigger{max-width:210px}}
</style><style>
.mark{display:block;width:34px;height:34px;object-fit:contain}
.case-heading{margin-bottom:32px}
.case-question+.result-section,.case-heading+.result-section{margin-top:8px}
.result-section>.section-label{margin-bottom:12px;color:#b4bbc2;font-size:13px;letter-spacing:.015em}
.result{padding:30px 32px;background:linear-gradient(180deg,#1b1e21 0%,#17191b 100%)}
.result h1,.result h2,.result h3{position:relative;color:#f4f6f7;letter-spacing:-.02em}
.result h1{padding-bottom:15px;border-bottom:1px solid #343a3e;color:#74d3f6;font-size:27px}
.result h2{padding:7px 0 7px 14px;color:#80d8f7;font-size:21px}
.result h2::before{content:"";position:absolute;left:0;top:8px;bottom:8px;width:3px;border-radius:99px;background:#54caf9}
.result h3{color:#c2eafa;font-size:17px}
.result strong{color:#fff;font-weight:700}
.result blockquote{margin:1.1em 0;padding:11px 15px;border-left:3px solid #54caf9;border-radius:0 8px 8px 0;background:#54caf90d;color:#c8d2d8}
.result table{overflow:hidden;border-radius:9px;background:#171a1c}
.result th{border-color:#3a4247;background:#242c30;color:#9ddff6}
.result td{border-color:#30363a}
.result tr:nth-child(even) td{background:#ffffff03}
</style></head>
<body><div class="shell"><aside class="sidebar"><div class="brand"><img class="mark" src="/assets/orgsight-logo.svg" alt=""><span>OrgSight</span></div><button id="new-analysis" class="new-analysis"><span>＋</span>新建分析</button><div class="side-label">已完成案例</div><nav id="case-list" class="case-list" aria-label="已完成案例"></nav></aside><section class="workspace"><header class="topbar"><div class="top-title">组织分析</div></header><main class="main"><section id="composer-view" class="composer-view"><h1 class="welcome">有什么需要一起分析的吗？</h1><div class="composer"><textarea id="prompt" aria-label="分析请求" rows="1" placeholder="请描述你希望分析的组织、人员或协作问题。"></textarea><div class="composer-bottom"><div class="team-picker"><button id="team-trigger" type="button" class="team-trigger" aria-haspopup="listbox" aria-expanded="false"><span id="team-trigger-label" class="team-trigger-label">选择分析方向</span><svg class="team-chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg></button><div id="team-menu" class="team-menu hidden" role="listbox" aria-label="分析方向"></div></div><button id="submit" class="submit">开始分析</button></div></div><div id="status" class="status" aria-live="polite"></div></section><article id="case-view" class="case-view hidden"><div id="case-kicker" class="case-kicker"></div><h1 id="case-heading" class="case-heading"></h1><section id="case-question" class="case-question"><div class="section-label">分析任务</div><div id="case-prompt" class="request-copy"></div></section><section class="result-section"><div id="result-label" class="section-label">任务结果</div><div id="result" class="result"></div></section></article></main></section></div>
<script>
const button=document.querySelector('#submit'),teamTrigger=document.querySelector('#team-trigger'),teamTriggerLabel=document.querySelector('#team-trigger-label'),teamMenu=document.querySelector('#team-menu'),prompt=document.querySelector('#prompt'),status=document.querySelector('#status'),result=document.querySelector('#result'),resultLabel=document.querySelector('#result-label'),caseList=document.querySelector('#case-list'),composerView=document.querySelector('#composer-view'),caseView=document.querySelector('#case-view'),newAnalysis=document.querySelector('#new-analysis');let timer=null,selectedLeader='';
function activeCase(id){for(const node of caseList.querySelectorAll('.case-button'))node.classList.toggle('active',node.dataset.caseId===id)}
function resizePrompt(){prompt.style.height='auto';const capped=prompt.scrollHeight>240;prompt.style.height=Math.min(Math.max(prompt.scrollHeight,52),240)+'px';prompt.style.overflowY=capped?'auto':'hidden'}
function showComposer(){clearInterval(timer);composerView.classList.remove('hidden');caseView.classList.add('hidden');activeCase('');status.textContent='';status.className='status';button.disabled=false;resizePrompt();prompt.focus()}
function escapeHtml(value){return String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]))}
function inlineMarkdown(value){return escapeHtml(value).replace(/`([^`]+)`/g,'<code>$1</code>').replace(/[*][*]([^*]+)[*][*]/g,'<strong>$1</strong>')}
function markdownToHtml(markdown){const lines=String(markdown||'').replace(/\r/g,'').split('\n'),html=[];let index=0;while(index<lines.length){const line=lines[index];if(!line.trim()){index++;continue}const heading=line.match(/^(#{1,3})\s+(.+)$/);if(heading){html.push('<h'+heading[1].length+'>'+inlineMarkdown(heading[2])+'</h'+heading[1].length+'>');index++;continue}if(/^---+$/.test(line.trim())){html.push('<hr>');index++;continue}if(/^\|.*\|\s*$/.test(line)&&index+1<lines.length&&/^\s*\|?\s*:?-{3,}/.test(lines[index+1])){const cells=value=>value.trim().replace(/^\||\|$/g,'').split('|').map(cell=>'<td>'+inlineMarkdown(cell.trim())+'</td>').join('');html.push('<table><thead><tr>'+cells(line).replaceAll('<td>','<th>').replaceAll('</td>','</th>')+'</tr></thead><tbody>');index+=2;while(index<lines.length&&/^\|.*\|\s*$/.test(lines[index])){html.push('<tr>'+cells(lines[index])+'</tr>');index++}html.push('</tbody></table>');continue}const list=line.match(/^(?:[-*+]\s+|\d+\.\s+)(.+)$/);if(list){const ordered=/^\d+\.\s+/.test(line),tag=ordered?'ol':'ul';html.push('<'+tag+'>');while(index<lines.length){const item=lines[index].match(ordered?/^\d+\.\s+(.+)$/:/^(?:[-*+]\s+)(.+)$/);if(!item)break;html.push('<li>'+inlineMarkdown(item[1])+'</li>');index++}html.push('</'+tag+'>');continue}const paragraph=[];while(index<lines.length&&lines[index].trim()&&!/^(#{1,3})\s+/.test(lines[index])&&!/^---+$/.test(lines[index].trim())&&!/^(?:[-*+]\s+|\d+\.\s+)/.test(lines[index])&&!/^\|.*\|\s*$/.test(lines[index])){paragraph.push(lines[index]);index++}html.push('<p>'+inlineMarkdown(paragraph.join(' '))+'</p>')}return html.join('')}
function formatCompletedAt(value,detail){if(!value)return '';const date=new Date(value);if(Number.isNaN(date.getTime()))return '';return date.toLocaleString('zh-CN',detail?{dateStyle:'medium',timeStyle:'short'}:{month:'short',day:'numeric'})}
function taskResultLabel(role){if(!role)return '任务结果';return (String(role).toLowerCase()==='worker'?'Worker':String(role))+' 的任务结果'}
function showState(data){status.className='status'+(data.status==='failed'||data.status==='timed_out'?' error':'');status.textContent=({queued:'等待提交',creating_source_room:'正在创建独立请求',waiting_for_leader:'等待 Team Leader 接收',processing:'正在分析并等待任务产出',completed:'分析完成',timed_out:'等待超时',failed:'处理失败'})[data.status]||data.status;if(data.error)status.textContent+='：'+data.error;if(data.result_markdown){composerView.classList.add('hidden');caseView.classList.remove('hidden');document.querySelector('#case-kicker').textContent='本次分析 · '+({completed:'已完成',timed_out:'等待超时',failed:'处理失败'})[data.status];document.querySelector('#case-heading').textContent='分析结果';document.querySelector('#case-question').classList.toggle('hidden',!String(data.prompt||'').trim());document.querySelector('#case-prompt').textContent=data.prompt||'';resultLabel.textContent='Worker 的任务结果';result.innerHTML=markdownToHtml(data.result_markdown);loadCases()}if(['completed','failed','timed_out'].includes(data.status)){button.disabled=false;clearInterval(timer)}}
async function poll(id){const response=await fetch('/api/requests/'+id);showState(await response.json())}
async function loadCase(caseId){const response=await fetch('/api/cases/'+encodeURIComponent(caseId));if(!response.ok)return;const data=await response.json();clearInterval(timer);composerView.classList.add('hidden');caseView.classList.remove('hidden');const completedAt=formatCompletedAt(data.completed_at,true),requestSummary=String(data.request_summary||'').trim();document.querySelector('#case-kicker').textContent=completedAt?'已完成案例 · '+completedAt:'已完成案例';document.querySelector('#case-heading').textContent=data.title;document.querySelector('#case-question').classList.toggle('hidden',!requestSummary);document.querySelector('#case-prompt').textContent=requestSummary;resultLabel.textContent=taskResultLabel(data.submitted_by_role);result.innerHTML=markdownToHtml(data.result_markdown);activeCase(data.case_id)}
async function loadCases(){const response=await fetch('/api/cases');if(!response.ok)return;const payload=await response.json();caseList.replaceChildren();for(const item of (payload.cases||[])){const card=document.createElement('button');card.className='case-button';card.dataset.caseId=item.case_id;card.innerHTML='<span class="case-title"></span><span class="case-meta"></span>';card.querySelector('.case-title').textContent=item.title;const completedAt=formatCompletedAt(item.completed_at,false),meta=card.querySelector('.case-meta');meta.textContent=completedAt?completedAt+' · 已完成':'已完成';card.onclick=()=>loadCase(item.case_id);caseList.append(card)}}
function closeTeamMenu(){teamMenu.classList.add('hidden');teamTrigger.setAttribute('aria-expanded','false')}
function selectTeam(value,label){selectedLeader=value;teamTriggerLabel.textContent=label;for(const node of teamMenu.querySelectorAll('button'))node.classList.toggle('active',node.dataset.leader===value);closeTeamMenu()}
async function loadLeaders(){const response=await fetch('/api/leaders');if(!response.ok)return;const payload=await response.json();teamMenu.replaceChildren();for(const item of (payload.leaders||[])){const option=document.createElement('button');option.type='button';option.dataset.leader=item.leader;option.setAttribute('role','option');option.innerHTML='<span class="team-menu-dot"></span><span></span>';option.lastElementChild.textContent=item.display_name;option.onclick=()=>selectTeam(item.leader,item.display_name);teamMenu.append(option)}const first=(payload.leaders||[])[0];if(first)selectTeam(first.leader,first.display_name)}
button.onclick=async()=>{const text=prompt.value.trim();if(!selectedLeader){status.className='status error';status.textContent='请选择分析方向。';return}if(!text){status.className='status error';status.textContent='请输入分析请求。';return}button.disabled=true;const response=await fetch('/api/requests',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:text,leader:selectedLeader})});const data=await response.json();if(!response.ok){status.className='status error';status.textContent=data.error||'提交失败';button.disabled=false;return}showState(data);timer=setInterval(()=>poll(data.request_id),2000)};
teamTrigger.onclick=()=>{const open=teamMenu.classList.toggle('hidden')===false;teamTrigger.setAttribute('aria-expanded',String(open))};document.addEventListener('click',event=>{if(!event.target.closest('.team-picker'))closeTeamMenu()});prompt.addEventListener('input',resizePrompt);newAnalysis.onclick=showComposer;loadLeaders();loadCases();resizePrompt();
</script></body></html>"""


async def read_body(receive: Any) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        chunks.append(message.get("body", b""))
        if not message.get("more_body"):
            return b"".join(chunks)


async def send_json(send: Any, status: int, body: dict[str, Any]) -> None:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json; charset=utf-8"), (b"content-length", str(len(payload)).encode())]})
    await send({"type": "http.response.body", "body": payload})


async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    if scope["type"] != "http":
        return
    method, path = scope["method"], scope["path"]
    if method == "GET" and path == "/":
        payload = INDEX_HTML.encode("utf-8")
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/html; charset=utf-8"), (b"content-length", str(len(payload)).encode())]})
        await send({"type": "http.response.body", "body": payload})
        return
    if method == "GET" and path == "/assets/orgsight-logo.svg":
        payload = LOGO_PATH.read_bytes()
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"image/svg+xml"), (b"content-length", str(len(payload)).encode())]})
        await send({"type": "http.response.body", "body": payload})
        return
    if method == "GET" and path == "/api/leaders":
        try:
            await send_json(send, 200, {"leaders": configured_leaders()})
        except (OSError, MatrixError) as error:
            await send_json(send, 500, {"error": str(error)})
        return
    if method == "POST" and path == "/api/requests":
        try:
            data = json.loads((await read_body(receive)).decode("utf-8"))
            prompt = data.get("prompt", "")
            leader = data.get("leader", "")
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError("请输入分析请求。")
            available = {item["leader"] for item in configured_leaders()}
            if not isinstance(leader, str) or leader not in available:
                raise ValueError("请选择有效的处理团队。")
            prompt = prompt.strip()
            if len(prompt) > MAX_REQUEST_LENGTH:
                raise ValueError(f"请求不得超过 {MAX_REQUEST_LENGTH} 个字符。")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            await send_json(send, 400, {"error": str(error)})
            return
        item = STORE.create(prompt, leader)
        threading.Thread(target=execute_request, args=(item.request_id,), daemon=True).start()
        await send_json(send, 202, asdict(item))
        return
    if method == "GET" and path.startswith("/api/requests/"):
        item = STORE.get(path.rsplit("/", 1)[-1])
        if item is None:
            await send_json(send, 404, {"error": "请求不存在或网页服务已重启。"})
            return
        await send_json(send, 200, asdict(item))
        return
    if method == "GET" and path == "/api/cases":
        try:
            await send_json(send, 200, agentteams_cases())
        except AgentTeamsCasesError as error:
            await send_json(send, 502, {"error": str(error)})
        return
    if method == "GET" and path.startswith("/api/cases/"):
        try:
            await send_json(send, 200, agentteams_case(path.rsplit("/", 1)[-1]))
        except AgentTeamsCasesError as error:
            await send_json(send, 502, {"error": str(error)})
        return
    await send_json(send, 404, {"error": "未找到页面。"})


def main() -> None:
    load_local_environment()
    host = os.environ.get("PROFILEMESH_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("PROFILEMESH_WEB_PORT", "8800"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
