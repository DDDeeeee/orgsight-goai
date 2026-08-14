from starlette.testclient import TestClient

from orgsight import mcp_server
from orgsight.authorization import TaskGrant
from orgsight.grant_service import TaskGrantRegistrationService
from orgsight.mcp_server import create_http_app, create_mcp
from orgsight.read_service import GoaiReadService

from test_read_service import FakeRepository


class GrantServiceStub:
    def __init__(self):
        self.payload = None

    def register(self, registration):
        self.payload = registration
        return TaskGrant(
            task_id=registration.task_id, worker_id=registration.worker_id,
            organization_id=registration.organization_id, snapshot_date=registration.snapshot_date,
            task_objective=registration.task_objective, allowed_tools=frozenset({"read_person_profile"}),
            allowed_person_ids=frozenset({"p_chen", "p_luo"}), allowed_unit_ids=frozenset({"sales"}),
            allowed_project_ids=frozenset(), status="active", expires_at=None,
        )

    def authorize_delegate(self, bearer_token):
        if bearer_token != "leader-token":
            from orgsight.grant_service import GrantRegistrationError
            raise GrantRegistrationError("调用身份无权登记 GOAI Task 授权")


def test_mcp_schema_is_closed_for_all_registered_tools():
    mcp = create_mcp(GoaiReadService(FakeRepository()))

    tools = mcp._tool_manager.list_tools()
    assert len(tools) == 17
    for tool in tools:
        assert tool.parameters["additionalProperties"] is False
        assert tool.parameters["properties"]["task_id"]["minLength"] == 1
        if tool.name != "resolve_authorized_person":
            assert tool.parameters["properties"]["snapshot_date"]["pattern"] == "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"


def test_docker_host_alias_passes_transport_security_check():
    app = create_http_app(GoaiReadService(FakeRepository()))

    with TestClient(app, base_url="http://host.docker.internal:8787") as client:
        response = client.get("/mcp")

    # GET without MCP's required Accept header is a protocol-level 406.
    # A rejected Host header would instead return 421.
    assert response.status_code == 406


def test_mcp_http_call_preserves_bearer_worker_identity():
    app = create_http_app(GoaiReadService(FakeRepository()))
    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "read_person_profile",
            "arguments": {
                "task_id": "task-person-001",
                "organization_id": "org-1",
                "snapshot_date": "2026-01-12",
                "person_id": "p_chen",
            },
        },
    }
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        "authorization": "Bearer worker-token",
    }

    with TestClient(app, base_url="http://host.docker.internal:8787") as client:
        response = client.post("/mcp", json=request, headers=headers)

    assert response.status_code == 200
    assert response.json()["result"]["structuredContent"]["status"] == "ok"
    assert response.json()["result"]["structuredContent"]["data"]["person_id"] == "p_chen"


def test_mcp_schema_rejects_spoofed_worker_id_before_business_logic():
    request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "read_person_profile",
            "arguments": {
                "task_id": "task-person-001",
                "organization_id": "org-1",
                "snapshot_date": "2026-01-12",
                "person_id": "p_chen",
                "worker_id": "spoofed",
            },
        },
    }
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        "authorization": "Bearer worker-token",
    }

    with TestClient(create_http_app(GoaiReadService(FakeRepository())), base_url="http://host.docker.internal:8787") as client:
        response = client.post("/mcp", json=request, headers=headers)

    assert response.status_code == 200
    assert response.json()["result"]["isError"] is True
    assert "Extra inputs are not permitted" in response.json()["result"]["content"][0]["text"]


def test_unrecognized_host_remains_blocked_by_transport_security():
    app = create_http_app(GoaiReadService(FakeRepository()))

    with TestClient(app, base_url="http://unrecognized.example:8787") as client:
        response = client.get("/mcp")

    assert response.status_code == 421


def test_unconfigured_port_remains_blocked_by_transport_security():
    app = create_http_app(GoaiReadService(FakeRepository()))

    with TestClient(app, base_url="http://host.docker.internal:9999") as client:
        response = client.get("/mcp")

    assert response.status_code == 421


def test_internal_grant_route_rejects_missing_or_invalid_controller_token():
    app = create_http_app(GoaiReadService(FakeRepository()), GrantServiceStub())
    payload = {"taskId": "task-001"}
    with TestClient(app, base_url="http://host.docker.internal:8787") as client:
        assert client.post("/internal/task-grants", json=payload).status_code == 401
        assert client.post("/internal/task-grants", json=payload, headers={"authorization": "Bearer wrong"}).status_code == 401


def test_internal_grant_route_registers_only_structured_template():
    stub = GrantServiceStub()
    payload = {
        "taskId": "task-001", "workerId": "person-profile-worker",
        "template": "person_role_fit_team_collaboration", "organizationId": "org-1",
        "snapshotDate": "2026-01-12", "subjectPersonId": "p_chen", "teamId": "sales",
    }
    with TestClient(create_http_app(GoaiReadService(FakeRepository()), stub), base_url="http://host.docker.internal:8787") as client:
        response = client.post("/internal/task-grants", json=payload, headers={"authorization": "Bearer leader-token"})
    assert response.status_code == 201
    assert response.json()["status"] == "registered"
    assert response.json()["allowedPersonCount"] == 2
    assert stub.payload.task_id == "task-001"


def test_internal_grant_route_rejects_worker_identity():
    with TestClient(create_http_app(GoaiReadService(FakeRepository()), GrantServiceStub()), base_url="http://host.docker.internal:8787") as client:
        response = client.post("/internal/task-grants", json={}, headers={"authorization": "Bearer worker-token"})
    assert response.status_code == 401


def test_main_loads_local_environment_before_selecting_uvicorn_address(monkeypatch):
    captured = {}

    def fake_load_environment():
        monkeypatch.setenv("ORGSIGHT_MCP_HOST", "127.0.0.1")
        monkeypatch.setenv("ORGSIGHT_MCP_PORT", "9999")

    monkeypatch.setattr(mcp_server, "load_local_environment", fake_load_environment)
    monkeypatch.setattr(mcp_server, "create_http_app", lambda: "app")
    monkeypatch.setattr(
        mcp_server.uvicorn,
        "run",
        lambda app, host, port: captured.update({"app": app, "host": host, "port": port}),
    )

    mcp_server.main()

    assert captured == {"app": "app", "host": "127.0.0.1", "port": 9999}
