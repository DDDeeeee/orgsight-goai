"""Task-scoped authorization for OrgSight GOAI MCP reads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
from typing import Any


class AuthorizationError(Exception):
    """Raised when a request is syntactically valid but outside its grant."""


@dataclass(frozen=True)
class TaskGrant:
    task_id: str
    worker_id: str
    organization_id: str
    snapshot_date: date
    task_objective: str
    allowed_tools: frozenset[str]
    allowed_person_ids: frozenset[str]
    allowed_unit_ids: frozenset[str]
    allowed_project_ids: frozenset[str]
    status: str
    expires_at: datetime | None

    def assert_request(self, tool_name: str, organization_id: str, snapshot_date: date) -> None:
        if self.status != "active" or (self.expires_at and self.expires_at <= datetime.now(self.expires_at.tzinfo)):
            raise AuthorizationError("Task 授权已失效")
        if tool_name not in self.allowed_tools:
            raise AuthorizationError("该 Task 未授权此工具")
        if organization_id != self.organization_id or snapshot_date != self.snapshot_date:
            raise AuthorizationError("组织或快照不属于该 Task")

    def assert_person(self, person_id: str) -> None:
        if person_id not in self.allowed_person_ids:
            raise AuthorizationError("该人员不属于 Task 授权范围")

    def assert_unit(self, unit_id: str) -> None:
        if unit_id not in self.allowed_unit_ids:
            raise AuthorizationError("该组织单元不属于 Task 授权范围")

    def assert_organization_scope(self) -> None:
        if self.organization_id not in self.allowed_unit_ids:
            raise AuthorizationError("该 Task 未获整个组织范围授权")

    def assert_project(self, project_id: str) -> None:
        if project_id not in self.allowed_project_ids:
            raise AuthorizationError("该项目不属于 Task 授权范围")


def token_sha256(bearer_token: str) -> str:
    """Hash a bearer token before looking it up; plaintext is never stored."""

    return hashlib.sha256(bearer_token.encode("utf-8")).hexdigest()


def json_list(value: Any) -> frozenset[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("授权记录中的列表字段无效")
    return frozenset(value)
