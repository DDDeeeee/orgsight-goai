"""HTTP MCP entrypoint exposing GOAI's seven currently available read tools."""

from __future__ import annotations

from contextvars import ContextVar
import os
import json
from pathlib import Path
from typing import Annotated, Any, Awaitable, Callable, Literal

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from dotenv import load_dotenv

from .read_service import GoaiReadService
from .repository import PostgresRepository
from .grant_service import GrantRegistration, TaskGrantRegistrationService, GrantRegistrationError


_bearer_token: ContextVar[str | None] = ContextVar("profilemesh_goai_bearer_token", default=None)
AsgiApp = Callable[[dict[str, Any], Callable[[], Awaitable[dict[str, Any]]], Callable[[dict[str, Any]], Awaitable[None]]], Awaitable[None]]
NonEmptyText = Annotated[str, Field(min_length=1)]
SnapshotDate = Annotated[str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")]
PositiveVersion = Annotated[int, Field(ge=1)]
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def load_local_environment() -> None:
    """Load only this repository's ignored local configuration, without overriding exports."""

    load_dotenv(REPOSITORY_ROOT / ".env", override=False)


class BearerContextMiddleware:
    """Makes the HTTP Authorization header available to individual MCP tools."""

    def __init__(self, app: AsgiApp) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable[[], Awaitable[dict[str, Any]]],
                       send: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        token: str | None = None
        if scope["type"] == "http":
            for name, value in scope.get("headers", []):
                if name.lower() == b"authorization":
                    scheme, _, candidate = value.decode("latin-1").partition(" ")
                    if scheme.lower() == "bearer" and candidate.strip():
                        token = candidate.strip()
                    break
        context_token = _bearer_token.set(token)
        try:
            await self.app(scope, receive, send)
        finally:
            _bearer_token.reset(context_token)


def create_mcp(service: GoaiReadService | None = None) -> FastMCP:
    """Build the MCP registry; service injection keeps business logic testable."""

    load_local_environment()
    read_service = service or GoaiReadService(PostgresRepository())
    host = os.environ.get("PROFILEMESH_GOAI_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("PROFILEMESH_GOAI_MCP_PORT", "8787"))
    local_hosts = [f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"]
    local_origins = [f"http://{value}" for value in local_hosts]
    mcp = FastMCP(
        "profilemesh-goai",
        instructions=(
            "OrgSight GOAI 的任务授权只读工具。每次调用必须带 task_id、"
            "organization_id 和 snapshot_date；服务端从 Bearer 凭证识别 Worker。"
            "在需要人员上下文时，先使用 resolve_authorized_person。"
        ),
        host=host,
        port=port,
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        # QwenPaw runs in Docker but the GOAI service remains on the host.
        # Keep DNS-rebinding protection enabled while accepting Docker's
        # documented host alias used by the stopped Worker manifests.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=local_hosts + [f"host.docker.internal:{port}"],
            allowed_origins=local_origins + [f"http://host.docker.internal:{port}"],
        ),
    )

    def common(task_id: str, organization_id: str, snapshot_date: str) -> dict[str, str | None]:
        return {
            "bearer_token": _bearer_token.get(), "task_id": task_id,
            "organization_id": organization_id, "snapshot_date": snapshot_date,
        }

    @mcp.tool(description="在当前 Task 的授权范围内按姓名解析唯一人员，并返回后续读取所需的组织、快照、人员与团队标识。必须先调用此工具，禁止猜测标识。")
    def resolve_authorized_person(task_id: NonEmptyText, person_name: NonEmptyText) -> dict[str, Any]:
        return read_service.resolve_authorized_person(
            bearer_token=_bearer_token.get(), task_id=task_id, person_name=person_name,
        )

    @mcp.tool(description="读取组织、岗位、成员与正式汇报关系。")
    def read_organization_structure(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate,
                                    scope_id: NonEmptyText | None = None, include_descendant_units: bool = True) -> dict[str, Any]:
        return read_service.read_organization_structure(
            **common(task_id, organization_id, snapshot_date), scope_id=scope_id,
            include_descendant_units=include_descendant_units,
        )

    @mcp.tool(description="读取当前组织快照中数据对象的可用性摘要，不返回档案或模型正文。")
    def read_organization_overview(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate) -> dict[str, Any]:
        return read_service.read_organization_overview(**common(task_id, organization_id, snapshot_date))

    @mcp.tool(description="读取任务已授权人员的完整职场事实档案，不包含人物模型。")
    def read_person_profile(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate, person_id: NonEmptyText) -> dict[str, Any]:
        return read_service.read_person_profile(**common(task_id, organization_id, snapshot_date), person_id=person_id)

    @mcp.tool(description="读取任务已授权人员的模型 Markdown 和原始 JSON。")
    def read_person_model(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate, person_id: NonEmptyText,
                          model_version: PositiveVersion | None = None) -> dict[str, Any]:
        return read_service.read_person_model(
            **common(task_id, organization_id, snapshot_date), person_id=person_id,
            model_version=model_version,
        )

    @mcp.tool(description="读取任务范围内某人员参与的无方向协作关系。")
    def read_person_collaboration_relations(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate,
                                            person_id: NonEmptyText, counterparty_person_ids: list[NonEmptyText] | None = None) -> dict[str, Any]:
        return read_service.read_person_collaboration_relations(
            **common(task_id, organization_id, snapshot_date), person_id=person_id,
            counterparty_person_ids=counterparty_person_ids,
        )

    @mcp.tool(description="读取任务已授权正式团队的成员、岗位与负责人。")
    def read_team_members(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate, team_id: NonEmptyText,
                          include_descendant_units: bool = False) -> dict[str, Any]:
        return read_service.read_team_members(
            **common(task_id, organization_id, snapshot_date), team_id=team_id,
            include_descendant_units=include_descendant_units,
        )

    @mcp.tool(description="读取任务已授权正式团队的内部和跨团队协作关系。")
    def read_team_collaboration_relations(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate,
                                          team_id: NonEmptyText, relation_scope: Literal["internal", "cross_team", "all"] = "all") -> dict[str, Any]:
        return read_service.read_team_collaboration_relations(
            **common(task_id, organization_id, snapshot_date), team_id=team_id,
            relation_scope=relation_scope,
        )

    @mcp.tool(description="读取已验收团队角色生态、健康与协作结构结果的汇总投影。")
    def read_team_model(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate, team_id: NonEmptyText,
                        components: list[Literal["role_ecology", "health", "collaboration_structure"]] | None = None) -> dict[str, Any]:
        return read_service.unavailable_team_result(
            **common(task_id, organization_id, snapshot_date), tool_name="read_team_model", team_id=team_id
        )

    @mcp.tool(description="读取已保存的团队角色生态评估；当前无已验收结果时返回 data_not_available。")
    def read_team_role_ecology(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate, team_id: NonEmptyText,
                               result_id: NonEmptyText | None = None) -> dict[str, Any]:
        return read_service.unavailable_team_result(
            **common(task_id, organization_id, snapshot_date), tool_name="read_team_role_ecology", team_id=team_id,
            result_id=result_id,
        )

    @mcp.tool(description="读取已保存的团队健康评估；当前无已验收结果时返回 data_not_available。")
    def read_team_health_assessment(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate, team_id: NonEmptyText,
                                    result_id: NonEmptyText | None = None) -> dict[str, Any]:
        return read_service.unavailable_team_result(
            **common(task_id, organization_id, snapshot_date), tool_name="read_team_health_assessment", team_id=team_id,
            result_id=result_id,
        )

    @mcp.tool(description="读取已保存的协作结构诊断；当前无已验收结果时返回 data_not_available。")
    def read_collaboration_structure_diagnosis(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate,
                                               scope_id: NonEmptyText, result_id: NonEmptyText | None = None) -> dict[str, Any]:
        return read_service.unavailable_scope_result(
            **common(task_id, organization_id, snapshot_date), tool_name="read_collaboration_structure_diagnosis", scope_id=scope_id,
            result_id=result_id,
        )

    @mcp.tool(description="读取项目原始材料；当前没有预制项目。")
    def read_project(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate, project_id: NonEmptyText) -> dict[str, Any]:
        return read_service.unavailable_project_result(
            **common(task_id, organization_id, snapshot_date), tool_name="read_project", project_id=project_id
        )

    @mcp.tool(description="读取已确认项目事件；当前没有预制项目。")
    def read_project_events(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate, project_id: NonEmptyText,
                            occurred_from: SnapshotDate | None = None, occurred_to: SnapshotDate | None = None) -> dict[str, Any]:
        return read_service.unavailable_project_result(
            **common(task_id, organization_id, snapshot_date), tool_name="read_project_events", project_id=project_id
        )

    @mcp.tool(description="读取已验收项目状态；当前没有预制项目。")
    def read_project_state(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate, project_id: NonEmptyText,
                           result_id: NonEmptyText | None = None) -> dict[str, Any]:
        return read_service.unavailable_project_result(
            **common(task_id, organization_id, snapshot_date), tool_name="read_project_state", project_id=project_id,
            result_id=result_id,
        )

    @mcp.tool(description="读取项目状态中的任务视图；当前没有预制项目。")
    def read_project_tasks(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate, project_id: NonEmptyText,
                           project_snapshot_id: NonEmptyText | None = None, work_item_ids: list[NonEmptyText] | None = None,
                           include_dependencies: bool = True, include_blockers: bool = True) -> dict[str, Any]:
        return read_service.unavailable_project_result(
            **common(task_id, organization_id, snapshot_date), tool_name="read_project_tasks", project_id=project_id
        )

    @mcp.tool(description="读取已保存的项目协作风险；当前没有预制项目。")
    def read_project_collaboration_risk(task_id: NonEmptyText, organization_id: NonEmptyText, snapshot_date: SnapshotDate,
                                        project_id: NonEmptyText, result_id: NonEmptyText | None = None) -> dict[str, Any]:
        return read_service.unavailable_project_result(
            **common(task_id, organization_id, snapshot_date), tool_name="read_project_collaboration_risk", project_id=project_id,
            result_id=result_id,
        )

    # FastMCP derives schemas from Python signatures. Make its generated schemas
    # match the contract's closed objects and reject unknown argument names.
    for tool in mcp._tool_manager.list_tools():
        tool.parameters["additionalProperties"] = False
        tool.fn_metadata.arg_model.model_config["extra"] = "forbid"
        tool.fn_metadata.arg_model.model_rebuild(force=True)

    return mcp


def create_http_app(service: GoaiReadService | None = None,
                    grant_service: TaskGrantRegistrationService | None = None) -> AsgiApp:
    """Return MCP plus the controlled internal Grant registration endpoint."""

    read_service = service or GoaiReadService(PostgresRepository())
    registration = grant_service or TaskGrantRegistrationService(PostgresRepository())
    mcp_app = BearerContextMiddleware(create_mcp(read_service).streamable_http_app())

    async def app(scope: dict[str, Any], receive: Callable[[], Awaitable[dict[str, Any]]],
                  send: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        if scope.get("type") == "http" and scope.get("path") == "/internal/task-grants" and scope.get("method") == "POST":
            body = b""
            while True:
                message = await receive()
                body += message.get("body", b"")
                if not message.get("more_body"):
                    break
            headers = {key.lower(): value for key, value in scope.get("headers", [])}
            authorization = headers.get(b"authorization", b"").decode("latin-1")
            token = authorization.split(" ", 1)[1].strip() if authorization.lower().startswith("bearer ") else None
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                if not isinstance(payload, dict):
                    raise GrantRegistrationError("请求体必须是 JSON 对象")
                registration.authorize_delegate(token)
                subject_name = payload.get("subjectPersonName")
                if isinstance(subject_name, str) and subject_name.strip():
                    try:
                        subject = registration.repository.person_by_name(subject_name.strip())
                    except NotFoundError as exc:
                        raise GrantRegistrationError("未找到唯一匹配的人员") from exc
                    payload = {
                        **payload,
                        "organizationId": subject["organization_id"],
                        "snapshotDate": subject["snapshot_date"].isoformat(),
                        "subjectPersonId": subject["person_id"],
                        "teamId": subject["unit_id"],
                    }
                grant = registration.register(GrantRegistration.from_payload(payload))
                response = {"status": "registered", "taskId": grant.task_id,
                            "allowedPersonCount": len(grant.allowed_person_ids)}
                status_code = 201
            except GrantRegistrationError as exc:
                response = {"status": "rejected", "error": str(exc)}
                status_code = 401 if "凭证" in str(exc) or "身份无权" in str(exc) else 400
            except (ValueError, json.JSONDecodeError) as exc:
                response = {"status": "rejected", "error": str(exc)}
                status_code = 400
            raw = json.dumps(response, ensure_ascii=False).encode("utf-8")
            await send({"type": "http.response.start", "status": status_code,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(raw)).encode())]})
            await send({"type": "http.response.body", "body": raw})
            return
        await mcp_app(scope, receive, send)
    return app


def main() -> None:
    load_local_environment()
    host = os.environ.get("PROFILEMESH_GOAI_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("PROFILEMESH_GOAI_MCP_PORT", "8787"))
    uvicorn.run(create_http_app(), host=host, port=port)


if __name__ == "__main__":
    main()
