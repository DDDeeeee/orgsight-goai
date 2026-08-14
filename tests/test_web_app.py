import pytest

from orgsight import web_app
from orgsight.web_app import (
	AgentTeamsCasesError,
	MatrixError,
	agentteams_case,
	agentteams_cases,
	completed_case_for_room,
	configured_leaders,
	configured_matrix_client,
)


def test_web_client_requires_its_own_human_credentials(monkeypatch):
    monkeypatch.setattr(web_app, "load_local_environment", lambda: None)
    monkeypatch.delenv("ORGSIGHT_WEB_MATRIX_USER", raising=False)
    monkeypatch.delenv("ORGSIGHT_WEB_MATRIX_PASSWORD", raising=False)
    monkeypatch.setenv("AGENTTEAMS_MATRIX_URL", "http://127.0.0.1:28080")

    with pytest.raises(MatrixError, match="ORGSIGHT_WEB_MATRIX_USER.*ORGSIGHT_WEB_MATRIX_PASSWORD"):
        configured_matrix_client()


def test_leaders_are_read_from_registry_without_frontend_case_data():
    assert configured_leaders() == [
        {"team": "talent-role-insight", "display_name": "人才与角色洞察", "leader": "talent-role-insight-lead"},
        {"team": "collaboration-governance", "display_name": "协作治理", "leader": "collaboration-governance-lead"},
        {"team": "business-operations", "display_name": "业务运营", "leader": "business-operations-lead"},
        {"team": "management-decision-simulation", "display_name": "管理决策模拟", "leader": "management-decision-simulation-lead"},
    ]


def test_completed_request_matches_new_case_by_source_room(monkeypatch):
    monkeypatch.setattr(web_app, "agentteams_cases", lambda: {"cases": [
        {"case_id": "old", "source_room_id": "matrix:!old:matrix.local"},
        {"case_id": "new", "source_room_id": "matrix:!source:matrix.local"},
    ]})
    monkeypatch.setattr(web_app, "agentteams_case", lambda case_id: {
        "case_id": case_id, "result_markdown": "# 真实结果",
    })

    assert completed_case_for_room("!source:matrix.local", {"old"}) == {
        "case_id": "new", "result_markdown": "# 真实结果",
    }


def test_completed_request_accepts_only_one_new_legacy_case(monkeypatch):
    monkeypatch.setattr(web_app, "agentteams_cases", lambda: {"cases": [
        {"case_id": "old"}, {"case_id": "new"},
    ]})
    monkeypatch.setattr(web_app, "agentteams_case", lambda case_id: {"case_id": case_id})

    assert completed_case_for_room("!source:matrix.local", {"old"}) == {"case_id": "new"}


def test_cases_are_read_from_agentteams_controller(monkeypatch):
    monkeypatch.setattr(web_app, "load_local_environment", lambda: None)
    monkeypatch.setenv("AGENTTEAMS_CONTROLLER_URL", "http://agentteams.test")
    seen: list[str] = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"cases":[]}'

    def fake_urlopen(request, timeout):
        seen.append(request.full_url)
        assert timeout == 10
        return Response()

    monkeypatch.setattr(web_app, "urlopen", fake_urlopen)

    assert agentteams_cases() == {"cases": []}
    assert seen == ["http://agentteams.test/api/v1/cases"]


def test_case_detail_rejects_path_traversal_before_any_request():
    with pytest.raises(AgentTeamsCasesError, match="案例标识无效"):
        agentteams_case("../not-a-case")


def test_web_page_contains_no_hardcoded_case_data():
    assert "OrgSight" in web_app.INDEX_HTML
    assert "Team Leader · AgentTeams" not in web_app.INDEX_HTML
    assert "管理侧工作台" not in web_app.INDEX_HTML
    assert "OrgSight 管理侧" not in web_app.INDEX_HTML
    assert "最多 2,000 个字符" not in web_app.INDEX_HTML
    assert "resize:none" in web_app.INDEX_HTML
    assert "resizePrompt" in web_app.INDEX_HTML
    assert 'id="team-trigger"' in web_app.INDEX_HTML
    assert 'id="team-menu"' in web_app.INDEX_HTML
    assert 'id="team-grid"' not in web_app.INDEX_HTML
    assert "叶琳" not in web_app.INDEX_HTML
    assert "供应商关系代表" not in web_app.INDEX_HTML
