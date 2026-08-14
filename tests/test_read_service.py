from datetime import date
import hashlib

from orgsight.authorization import TaskGrant, token_sha256
from orgsight.grant_service import GrantRegistration, TaskGrantRegistrationService
from orgsight.read_service import GoaiReadService
from orgsight.repository import ModelDocumentUnavailableError, NotFoundError


class FakeRepository:
    def __init__(self):
        self.tokens = {token_sha256("worker-token"): "person-profile-worker"}
        self.grant = TaskGrant(
            task_id="task-person-001", worker_id="person-profile-worker",
            organization_id="org-1", snapshot_date=date(2026, 1, 12), task_objective="评估人员的岗位适配与协作特征",
            allowed_tools=frozenset({"read_person_profile", "read_person_collaboration_relations", "read_organization_structure"}),
            allowed_person_ids=frozenset({"p_chen", "p_luo"}), allowed_unit_ids=frozenset({"sales"}),
            allowed_project_ids=frozenset(), status="active", expires_at=None,
        )

    def resolve_worker(self, token): return self.tokens.get(token_sha256(token))
    def get_grant(self, task_id): return self.grant if task_id == self.grant.task_id else None
    def person_profile(self, organization_id, snapshot_date, person_id):
        assert (organization_id, snapshot_date, person_id) == ("org-1", date(2026, 1, 12), "p_chen")
        return {"person_id": "p_chen", "name": "陈远", "formal_title": "经理", "unit_id": "sales",
                "formal_manager_person_id": None, "functional_manager": None, "employment_type": "employee",
                "formal_structure_note": None, "profile_json": {"person_id": "p_chen", "name": "陈远", "career_stage": "负责人"}}
    def relationships(self, organization_id, snapshot_date):
        return {"relationship_snapshot_id": "rel-1", "status": "active"}, [
            {"member_a_person_id": "p_chen", "member_b_person_id": "p_luo", "relationship_type": "协作", "valence": "positive", "salience": 4, "summary": "合作顺畅", "risk": "需明确边界"},
            {"member_a_person_id": "p_chen", "member_b_person_id": "p_hidden", "relationship_type": "协作", "valence": "neutral", "salience": 2, "summary": "不应泄露", "risk": "无"},
        ]
    def project_exists(self, organization_id, snapshot_date, project_id): return False


class OrganizationRepository(FakeRepository):
    def __init__(self, *, whole_organization=False, relationship_snapshot=True):
        super().__init__()
        self.grant = TaskGrant(
            **{
                **self.grant.__dict__,
                "allowed_tools": frozenset({
                    "read_organization_overview", "read_organization_structure",
                    "read_person_model", "read_team_members", "read_team_collaboration_relations",
                }),
                "allowed_unit_ids": frozenset({"org-1", "sales", "sales-east"})
                if whole_organization else frozenset({"sales", "sales-east"}),
                "allowed_person_ids": frozenset({"p_chen", "p_luo", "p_east"}),
            }
        )
        self.has_relationship_snapshot = relationship_snapshot

    def organization(self, organization_id, snapshot_date):
        if (organization_id, snapshot_date) != ("org-1", date(2026, 1, 12)):
            raise NotFoundError
        return {"organization_id": "org-1", "snapshot_date": "2026-01-12", "display_name": "测试组织", "scope": "测试", "status": "active"}

    def units(self, organization_id, snapshot_date):
        return [
            {"unit_id": "sales", "name": "销售", "parent_unit_id": None, "manager_person_id": "p_chen"},
            {"unit_id": "sales-east", "name": "东区销售", "parent_unit_id": "sales", "manager_person_id": "p_east"},
        ]

    def people(self, organization_id, snapshot_date):
        return [
            {"person_id": "p_chen", "name": "陈远", "formal_title": "经理", "unit_id": "sales", "formal_manager_person_id": None, "functional_manager": None, "employment_type": "employee", "formal_structure_note": None},
            {"person_id": "p_luo", "name": "罗峻", "formal_title": "代表", "unit_id": "sales", "formal_manager_person_id": "p_chen", "functional_manager": None, "employment_type": "employee", "formal_structure_note": None},
            {"person_id": "p_east", "name": "东区成员", "formal_title": "代表", "unit_id": "sales-east", "formal_manager_person_id": "p_chen", "functional_manager": None, "employment_type": "employee", "formal_structure_note": None},
        ]

    def overview_availability(self, organization_id, snapshot_date):
        return {"person_profiles": True, "person_models": True, "relationships": self.has_relationship_snapshot,
                "team_role_ecology_assessments": False, "team_health_assessments": False,
                "collaboration_structure_diagnoses": False, "projects": False}

    def relationship_snapshot(self, organization_id, snapshot_date):
        if not self.has_relationship_snapshot:
            return None
        return {"relationship_snapshot_id": "rel-1", "status": "active"}

    def person_model(self, organization_id, snapshot_date, person_id, model_version):
        return {"model_document_id": "model-chen", "model_version": 1, "model_status": "active", "model_json": {"person_id": person_id}, "relative_path": "data/model-documents/person-chen.md"}

    def model_markdown(self, relative_path):
        return "# 陈远\n\n模型正文\n"


class GrantRegistrationRepository(OrganizationRepository):
    def __init__(self):
        super().__init__()
        self.registered = None

    def upsert_task_grant(self, **kwargs):
        self.registered = kwargs
        return TaskGrant(
            task_id=kwargs["task_id"], worker_id=kwargs["worker_id"],
            organization_id=kwargs["organization_id"], snapshot_date=kwargs["snapshot_date"],
            task_objective=kwargs["task_objective"], allowed_tools=kwargs["allowed_tools"],
            allowed_person_ids=kwargs["allowed_person_ids"], allowed_unit_ids=kwargs["allowed_unit_ids"],
            allowed_project_ids=kwargs["allowed_project_ids"], status="active", expires_at=None,
        )


class NoReadOnDeniedRepository(OrganizationRepository):
    def organization(self, *args):
        raise AssertionError("denied request must not read the organization")

    def units(self, *args):
        raise AssertionError("denied request must not read organization units")

    def people(self, *args):
        raise AssertionError("denied request must not read people")

    def overview_availability(self, *args):
        raise AssertionError("denied request must not read availability")

    def relationship_snapshot(self, *args):
        raise AssertionError("denied request must not read relationships")


def request():
    return {"bearer_token": "worker-token", "task_id": "task-person-001", "organization_id": "org-1", "snapshot_date": "2026-01-12"}


def test_authorized_person_profile_returns_profile_without_identity_duplication():
    result = GoaiReadService(FakeRepository()).read_person_profile(**request(), person_id="p_chen")
    assert result["status"] == "ok"
    assert result["data"]["profile"] == {"career_stage": "负责人"}
    assert result["references"][0]["ref_type"] == "person_profile"


def test_task_objective_is_descriptive_and_does_not_change_authorization():
    repository = FakeRepository()
    repository.grant = TaskGrant(**{
        **repository.grant.__dict__,
        "task_objective": "核对销售团队当前角色覆盖与协作风险，再形成管理侧诊断输入",
    })

    result = GoaiReadService(repository).read_person_profile(**request(), person_id="p_chen")

    assert result["status"] == "ok"


def test_out_of_scope_person_is_denied_before_repository_read():
    result = GoaiReadService(FakeRepository()).read_person_profile(**request(), person_id="p_hidden")
    assert result["status"] == "access_denied"


def test_person_relation_read_filters_ungranted_counterparties():
    result = GoaiReadService(FakeRepository()).read_person_collaboration_relations(**request(), person_id="p_chen")
    assert result["status"] == "ok"
    assert [edge["member_b"] for edge in result["data"]["relations"]] == ["p_luo"]


def test_snapshot_outside_task_grant_is_denied():
    result = GoaiReadService(FakeRepository()).read_person_profile(
        **{**request(), "snapshot_date": "2026-01-13"}, person_id="p_chen"
    )
    assert result["status"] == "access_denied"


def test_other_worker_cannot_distinguish_another_workers_task_from_missing_task():
    repository = FakeRepository()
    repository.tokens[token_sha256("other-worker-token")] = "other-worker"
    service = GoaiReadService(repository)
    owned_by_someone_else = service.read_person_profile(
        **{**request(), "bearer_token": "other-worker-token"}, person_id="p_chen"
    )
    missing_task = service.read_person_profile(
        **{**request(), "bearer_token": "other-worker-token", "task_id": "task-missing"}, person_id="p_chen"
    )
    assert owned_by_someone_else["status"] == missing_task["status"] == "not_found"


def test_absent_project_is_not_reported_as_merely_unavailable_data():
    repository = FakeRepository()
    repository.grant = TaskGrant(**{
        **repository.grant.__dict__,
        "allowed_tools": frozenset({"read_project"}),
        "allowed_project_ids": frozenset({"project-missing"}),
    })
    result = GoaiReadService(repository).unavailable_project_result(
        **request(), tool_name="read_project", project_id="project-missing"
    )
    assert result["status"] == "not_found"


def test_specified_result_id_is_not_reported_as_merely_unavailable_data():
    repository = OrganizationRepository()
    repository.grant = TaskGrant(**{
        **repository.grant.__dict__,
        "allowed_tools": frozenset({"read_team_role_ecology"}),
    })
    result = GoaiReadService(repository).unavailable_team_result(
        **request(), tool_name="read_team_role_ecology", team_id="sales", result_id="result-missing"
    )
    assert result["status"] == "not_found"


def test_organization_overview_requires_explicit_whole_organization_scope():
    result = GoaiReadService(OrganizationRepository()).read_organization_overview(**request())
    assert result["status"] == "access_denied"


def test_denied_organization_overview_does_not_read_any_organization_data():
    result = GoaiReadService(NoReadOnDeniedRepository()).read_organization_overview(**request())
    assert result["status"] == "access_denied"


def test_organization_overview_allows_absent_relationship_snapshot():
    result = GoaiReadService(OrganizationRepository(whole_organization=True, relationship_snapshot=False)).read_organization_overview(**request())
    assert result["status"] == "ok"
    assert result["data"]["available_data"]["relationship_snapshot_id"] is None


def test_descendant_units_must_be_explicitly_authorized():
    repository = OrganizationRepository()
    repository.grant = TaskGrant(**{**repository.grant.__dict__, "allowed_unit_ids": frozenset({"sales"})})
    result = GoaiReadService(repository).read_organization_structure(**request(), scope_id="sales", include_descendant_units=True)
    assert result["status"] == "access_denied"


def test_denied_organization_structure_scope_does_not_read_any_organization_data():
    repository = NoReadOnDeniedRepository()
    result = GoaiReadService(repository).read_organization_structure(**request(), scope_id="not-authorized")
    assert result["status"] == "access_denied"


def test_person_model_reference_hash_matches_returned_markdown():
    result = GoaiReadService(OrganizationRepository()).read_person_model(**request(), person_id="p_chen")
    assert result["status"] == "ok"
    markdown = result["data"]["model"]["markdown"]
    assert result["references"][0]["content_sha256"] == hashlib.sha256(markdown.encode("utf-8")).hexdigest()


def test_invalid_model_document_path_returns_structured_unavailable_response():
    repository = OrganizationRepository()
    repository.model_markdown = lambda relative_path: (_ for _ in ()).throw(ValueError("invalid path"))
    result = GoaiReadService(repository).read_person_model(**request(), person_id="p_chen")
    assert result["status"] == "data_not_available"
    assert result["data"] is None


def test_missing_model_document_returns_structured_unavailable_response():
    repository = OrganizationRepository()
    repository.model_markdown = lambda relative_path: (_ for _ in ()).throw(ModelDocumentUnavailableError())
    result = GoaiReadService(repository).read_person_model(**request(), person_id="p_chen")
    assert result["status"] == "data_not_available"
    assert result["data"] is None


def test_team_relationship_response_does_not_expose_excluded_edge_count():
    repository = OrganizationRepository()
    repository.relationships = lambda organization_id, snapshot_date: (
        {"relationship_snapshot_id": "rel-1", "status": "active"},
        [
            {"member_a_person_id": "p_chen", "member_b_person_id": "p_luo", "relationship_type": "协作", "valence": "positive", "salience": 3, "summary": "内部", "risk": "无"},
            {"member_a_person_id": "p_chen", "member_b_person_id": "p_hidden", "relationship_type": "协作", "valence": "neutral", "salience": 2, "summary": "外部", "risk": "无"},
        ],
    )
    result = GoaiReadService(repository).read_team_collaboration_relations(**request(), team_id="sales")
    assert result["status"] == "ok"
    assert "excluded_relation_count" not in result["data"]
    assert result["data"]["cross_team_relations"] == []


def test_role_fit_template_expands_team_scope_and_all_required_read_tools():
    repository = GrantRegistrationRepository()
    grant = TaskGrantRegistrationService(repository).register(GrantRegistration.from_payload({
        "taskId": "role-fit-001", "workerId": "person-profile-worker",
        "template": "person_role_fit_team_collaboration", "organizationId": "org-1",
        "snapshotDate": "2026-01-12", "subjectPersonId": "p_chen", "teamId": "sales",
    }))

    assert grant.allowed_person_ids == {"p_chen", "p_luo", "p_east"}
    assert grant.allowed_unit_ids == {"sales", "sales-east"}
    assert grant.allowed_tools == {
        "resolve_authorized_person",
        "read_organization_structure", "read_person_profile", "read_person_model",
        "read_person_collaboration_relations", "read_team_members",
        "read_team_collaboration_relations",
    }


def test_role_fit_template_rejects_subject_outside_team_scope():
    repository = GrantRegistrationRepository()
    registration = GrantRegistration.from_payload({
        "taskId": "role-fit-001", "workerId": "person-profile-worker",
        "template": "person_role_fit_team_collaboration", "organizationId": "org-1",
        "snapshotDate": "2026-01-12", "subjectPersonId": "p_unknown", "teamId": "sales",
    })

    import pytest
    with pytest.raises(ValueError, match="不属于指定团队范围"):
        TaskGrantRegistrationService(repository).register(registration)
