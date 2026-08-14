"""Controlled registration of GOAI Task Grants before a Worker is notified."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .authorization import TaskGrant
from .repository import NotFoundError, PostgresRepository


PERSON_ROLE_FIT_TEAM_COLLABORATION = "person_role_fit_team_collaboration"
PERSON_ROLE_FIT_WORKERS = frozenset({
    "person-profile-worker",
    "role-and-position-analysis-worker",
})
PERSON_ROLE_FIT_TOOLS = frozenset({
    "resolve_authorized_person",
    "read_organization_structure",
    "read_person_profile",
    "read_person_model",
    "read_person_collaboration_relations",
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
    subject_person_id: str
    team_id: str
    task_objective: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "GrantRegistration":
        required = {
            "taskId": "task_id",
            "workerId": "worker_id",
            "template": "template",
            "organizationId": "organization_id",
            "snapshotDate": "snapshot_date",
            "subjectPersonId": "subject_person_id",
            "teamId": "team_id",
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
        return cls(
            task_id=values["task_id"], worker_id=values["worker_id"], template=values["template"],
            organization_id=values["organization_id"], snapshot_date=snapshot_date,
            subject_person_id=values["subject_person_id"], team_id=values["team_id"],
            task_objective=task_objective.strip() or "岗位适配与团队协作分析",
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
        if registration.template != PERSON_ROLE_FIT_TEAM_COLLABORATION:
            raise GrantRegistrationError("不支持的授权模板")
        if registration.worker_id not in PERSON_ROLE_FIT_WORKERS:
            raise GrantRegistrationError("该模板不适用于此 Worker")
        try:
            self.repository.organization(registration.organization_id, registration.snapshot_date)
            units = self.repository.units(registration.organization_id, registration.snapshot_date)
            people = self.repository.people(registration.organization_id, registration.snapshot_date)
        except NotFoundError as error:
            raise GrantRegistrationError("组织或快照不存在") from error

        unit_ids = {unit["unit_id"] for unit in units}
        if registration.team_id not in unit_ids:
            raise GrantRegistrationError("teamId 不是当前快照的正式组织单元")
        team_units = self._descendants(units, registration.team_id)
        team_people = {person["person_id"] for person in people if person["unit_id"] in team_units}
        if registration.subject_person_id not in team_people:
            raise GrantRegistrationError("subjectPersonId 不属于指定团队范围")

        return self.repository.upsert_task_grant(
            task_id=registration.task_id,
            worker_id=registration.worker_id,
            organization_id=registration.organization_id,
            snapshot_date=registration.snapshot_date,
            task_objective=registration.task_objective,
            allowed_tools=PERSON_ROLE_FIT_TOOLS,
            allowed_person_ids=team_people,
            allowed_unit_ids=team_units,
            allowed_project_ids=frozenset(),
        )
