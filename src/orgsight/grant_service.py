"""Controlled registration of GOAI Task Grants before a Worker is notified."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .authorization import TaskGrant
from .repository import NotFoundError, PostgresRepository


PERSON_ROLE_FIT_TEAM_COLLABORATION = "person_role_fit_team_collaboration"
PERSON_PROFESSIONAL_PROFILE = "person_professional_profile"
TEAM_ROLE_ECOLOGY = "team_role_ecology"
PERSON_ROLE_FIT_WORKERS = frozenset({"role-and-position-analysis-worker"})
PERSON_ROLE_FIT_TOOLS = frozenset({
    "resolve_authorized_person",
    "read_organization_structure",
    "read_person_profile",
    "read_person_model",
    "read_person_collaboration_relations",
    "read_team_members",
    "read_team_collaboration_relations",
})
PERSON_PROFESSIONAL_PROFILE_TOOLS = frozenset({
    "resolve_authorized_person",
    "read_person_profile",
    "read_person_model",
    "read_person_collaboration_relations",
})
TEAM_ROLE_ECOLOGY_TOOLS = frozenset({
    "resolve_authorized_team",
    "read_organization_structure",
    "read_person_profile",
    "read_person_model",
    "read_team_members",
    "read_team_collaboration_relations",
})


class GrantRegistrationError(ValueError):
    """Raised when an internal caller requests an invalid or unsafe Grant."""


@dataclass(frozen=True)
class GrantRegistration:
    """Structured, minimal input accepted from the AgentTeams delegation hook."""

    task_id: str
    worker_id: str
    template: str
    organization_id: str
    snapshot_date: date
    subject_person_id: str | None
    team_id: str | None
    task_objective: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "GrantRegistration":
        required = {
            "taskId": "task_id",
            "workerId": "worker_id",
            "template": "template",
            "organizationId": "organization_id",
            "snapshotDate": "snapshot_date",
        }
        values: dict[str, str] = {}
        for key, field in required.items():
            value = payload.get(key)
            if not isinstance(value, str) or not value.strip():
                raise GrantRegistrationError(f"{key} 必须是非空字符串")
            values[field] = value.strip()
        try:
            snapshot_date = date.fromisoformat(values["snapshot_date"])
        except ValueError as error:
            raise GrantRegistrationError("snapshotDate 必须是 YYYY-MM-DD") from error
        task_objective = payload.get("taskObjective", "")
        if not isinstance(task_objective, str):
            raise GrantRegistrationError("taskObjective 必须是字符串")
        subject_person_id = payload.get("subjectPersonId")
        team_id = payload.get("teamId")
        if subject_person_id is not None and (not isinstance(subject_person_id, str) or not subject_person_id.strip()):
            raise GrantRegistrationError("subjectPersonId 必须是非空字符串")
        if team_id is not None and (not isinstance(team_id, str) or not team_id.strip()):
            raise GrantRegistrationError("teamId 必须是非空字符串")
        if values["template"] == PERSON_PROFESSIONAL_PROFILE:
            if not subject_person_id:
                raise GrantRegistrationError("人物画像授权需要 subjectPersonId")
            if team_id:
                raise GrantRegistrationError("人物画像授权只接受 subjectPersonId，且不接受 teamId")
        elif values["template"] == TEAM_ROLE_ECOLOGY:
            if not team_id:
                raise GrantRegistrationError("团队生态授权需要 teamId")
            if subject_person_id:
                raise GrantRegistrationError("团队生态授权只接受 teamId，且不接受 subjectPersonId")
        elif values["template"] == PERSON_ROLE_FIT_TEAM_COLLABORATION:
            if not subject_person_id or not team_id:
                raise GrantRegistrationError("岗位适配授权需要 subjectPersonId 和 teamId")
        return cls(
            task_id=values["task_id"], worker_id=values["worker_id"], template=values["template"],
            organization_id=values["organization_id"], snapshot_date=snapshot_date,
            subject_person_id=subject_person_id.strip() if isinstance(subject_person_id, str) else None,
            team_id=team_id.strip() if isinstance(team_id, str) else None,
            task_objective=task_objective.strip() or "组织分析任务",
        )


class TaskGrantRegistrationService:
    """Expands audited authorization templates; callers cannot choose raw scopes."""

    def __init__(self, repository: PostgresRepository) -> None:
        self.repository = repository

    def authorize_delegate(self, bearer_token: str | None) -> None:
        """Allow only the registered GOAI Team Leader to create a Worker Grant."""

        if not bearer_token:
            raise GrantRegistrationError("缺少内部调用凭证")
        worker_id = self.repository.resolve_worker(bearer_token)
        if worker_id != "talent-role-insight-lead":
            raise GrantRegistrationError("调用身份无权登记 GOAI Task 授权")

    @staticmethod
    def _descendants(units: list[dict[str, Any]], root_unit_id: str) -> set[str]:
        children: dict[str | None, list[str]] = {}
        for unit in units:
            children.setdefault(unit["parent_unit_id"], []).append(unit["unit_id"])
        selected = {root_unit_id}
        pending = [root_unit_id]
        while pending:
            parent = pending.pop()
            for child in children.get(parent, []):
                if child not in selected:
                    selected.add(child)
                    pending.append(child)
        return selected

    def register(self, registration: GrantRegistration) -> TaskGrant:
        try:
            self.repository.organization(registration.organization_id, registration.snapshot_date)
            units = self.repository.units(registration.organization_id, registration.snapshot_date)
            people = self.repository.people(registration.organization_id, registration.snapshot_date)
        except NotFoundError as error:
            raise GrantRegistrationError("组织或快照不存在") from error

        unit_ids = {unit["unit_id"] for unit in units}
        people_by_id = {person["person_id"]: person for person in people}

        if registration.template == PERSON_ROLE_FIT_TEAM_COLLABORATION:
            if registration.worker_id not in PERSON_ROLE_FIT_WORKERS:
                raise GrantRegistrationError("该模板不适用于此 Worker")
            if not registration.subject_person_id or not registration.team_id:
                raise GrantRegistrationError("岗位适配授权需要 subjectPersonId 和 teamId")
            if registration.team_id not in unit_ids:
                raise GrantRegistrationError("teamId 不是当前快照的正式组织单元")
            team_units = self._descendants(units, registration.team_id)
            team_people = {person["person_id"] for person in people if person["unit_id"] in team_units}
            if registration.subject_person_id not in team_people:
                raise GrantRegistrationError("subjectPersonId 不属于指定团队范围")
            allowed_tools, allowed_people, allowed_units = (
                PERSON_ROLE_FIT_TOOLS, team_people, team_units,
            )
        elif registration.template == PERSON_PROFESSIONAL_PROFILE:
            if registration.worker_id != "person-profile-worker":
                raise GrantRegistrationError("该模板不适用于此 Worker")
            subject = people_by_id.get(registration.subject_person_id)
            if not subject:
                raise GrantRegistrationError("subjectPersonId 不是当前快照中的人员")
            allowed_tools = PERSON_PROFESSIONAL_PROFILE_TOOLS
            # Direct relationships are a permitted view of the subject's own
            # record, but their counterparties are not independently readable.
            allowed_people = {registration.subject_person_id}
            allowed_units = {subject["unit_id"]}
        elif registration.template == TEAM_ROLE_ECOLOGY:
            if registration.worker_id != "team-role-ecology-worker":
                raise GrantRegistrationError("该模板不适用于此 Worker")
            if registration.team_id not in unit_ids:
                raise GrantRegistrationError("teamId 不是当前快照的正式组织单元")
            allowed_units = self._descendants(units, registration.team_id)
            allowed_people = {person["person_id"] for person in people if person["unit_id"] in allowed_units}
            allowed_tools = TEAM_ROLE_ECOLOGY_TOOLS
        else:
            raise GrantRegistrationError("不支持的授权模板")

        return self.repository.upsert_task_grant(
            task_id=registration.task_id,
            worker_id=registration.worker_id,
            organization_id=registration.organization_id,
            snapshot_date=registration.snapshot_date,
            task_objective=registration.task_objective,
            allowed_tools=allowed_tools,
            allowed_person_ids=allowed_people,
            allowed_unit_ids=allowed_units,
            allowed_project_ids=frozenset(),
        )
