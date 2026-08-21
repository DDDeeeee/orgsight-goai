"""Business behaviour of the seven implemented, task-authorized read tools."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from typing import Any

from .authorization import AuthorizationError, TaskGrant
from .repository import ModelDocumentUnavailableError, NotFoundError, PostgresRepository


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def response(status: str, data: Any = None, references: list[dict[str, str]] | None = None,
             missing_information: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "data": data,
        "references": references or [],
        "missing_information": missing_information or [],
    }


class GoaiReadService:
    """A service layer kept independent of MCP transport for direct testing."""

    def __init__(self, repository: PostgresRepository) -> None:
        self.repository = repository

    @staticmethod
    def parse_snapshot(snapshot_date: str) -> date | None:
        try:
            return date.fromisoformat(snapshot_date)
        except (TypeError, ValueError):
            return None

    def authorize(self, bearer_token: str | None, task_id: str, tool_name: str,
                  organization_id: str, snapshot_date: str) -> tuple[TaskGrant | None, dict[str, Any] | None]:
        parsed_date = self.parse_snapshot(snapshot_date)
        if not task_id or not organization_id or parsed_date is None:
            return None, response("input_invalid", missing_information=["task_id、organization_id 和 snapshot_date 必须有效"])
        if not bearer_token:
            return None, response("access_denied", missing_information=["缺少 Worker 凭证"])
        worker_id = self.repository.resolve_worker(bearer_token)
        if not worker_id:
            return None, response("access_denied", missing_information=["无法鉴别调用 Worker"])
        grant = self.repository.get_grant(task_id)
        if grant and grant.worker_id != worker_id:
            # Do not let one authenticated Worker discover another Worker's
            # Task IDs by comparing not_found and access_denied responses.
            return None, response("not_found", missing_information=["Task 授权不存在"])
        if not grant:
            return None, response("not_found", missing_information=["Task 授权不存在"])
        try:
            grant.assert_request(tool_name, organization_id, parsed_date)
        except AuthorizationError as error:
            return None, response("access_denied", missing_information=[str(error)])
        return grant, None

    def resolve_authorized_person(self, *, bearer_token: str | None, task_id: str,
                                  person_name: str) -> dict[str, Any]:
        """Resolve an explicitly named person only inside the caller's Task Grant.

        This is the bootstrap read for Workers: it exposes the identifiers required
        by the remaining task-scoped tools, without allowing an unrestricted name
        search or exposing anyone outside the Grant.
        """
        if not task_id or not person_name or not person_name.strip():
            return response("input_invalid", missing_information=["task_id 和 person_name 必须有效"])
        if not bearer_token:
            return response("access_denied", missing_information=["缺少 Worker 凭证"])
        worker_id = self.repository.resolve_worker(bearer_token)
        if not worker_id:
            return response("access_denied", missing_information=["无法鉴别调用 Worker"])
        grant = self.repository.get_grant(task_id)
        if not grant or grant.worker_id != worker_id:
            return response("not_found", missing_information=["Task 授权不存在"])
        try:
            grant.assert_request("resolve_authorized_person", grant.organization_id, grant.snapshot_date)
        except AuthorizationError as error:
            return response("access_denied", missing_information=[str(error)])
        try:
            people = self.repository.people(grant.organization_id, grant.snapshot_date)
        except NotFoundError:
            return response("not_found")
        matches = [person for person in people if person["name"] == person_name.strip()
                   and person["person_id"] in grant.allowed_person_ids]
        if len(matches) != 1:
            return response("not_found", missing_information=["授权范围内未找到唯一匹配的人员"])
        person = matches[0]
        data = {
            "organization_id": grant.organization_id,
            "snapshot_date": str(grant.snapshot_date),
            "person_id": person["person_id"],
            "person_name": person["name"],
            "team_id": person["unit_id"],
            "formal_title": person["formal_title"],
        }
        return response("ok", data, [{"ref_type": "task_grant", "ref_id": task_id,
                                       "ref_version": str(grant.snapshot_date),
                                       "content_sha256": canonical_hash(data)}])

    def resolve_authorized_team(self, *, bearer_token: str | None, task_id: str,
                                team_name: str) -> dict[str, Any]:
        """Resolve one formal team only when it is already inside this Task Grant."""
        if not task_id or not team_name or not team_name.strip():
            return response("input_invalid", missing_information=["task_id 和 team_name 必须有效"])
        if not bearer_token:
            return response("access_denied", missing_information=["缺少 Worker 凭证"])
        worker_id = self.repository.resolve_worker(bearer_token)
        if not worker_id:
            return response("access_denied", missing_information=["无法鉴别调用 Worker"])
        grant = self.repository.get_grant(task_id)
        if not grant or grant.worker_id != worker_id:
            return response("not_found", missing_information=["Task 授权不存在"])
        try:
            grant.assert_request("resolve_authorized_team", grant.organization_id, grant.snapshot_date)
            units = self.repository.units(grant.organization_id, grant.snapshot_date)
        except AuthorizationError as error:
            return response("access_denied", missing_information=[str(error)])
        except NotFoundError:
            return response("not_found")
        matches = [unit for unit in units if unit["name"] == team_name.strip()
                   and unit["unit_id"] in grant.allowed_unit_ids]
        if len(matches) != 1:
            return response("not_found", missing_information=["授权范围内未找到唯一匹配的正式团队"])
        team = matches[0]
        data = {"organization_id": grant.organization_id, "snapshot_date": str(grant.snapshot_date),
                "team_id": team["unit_id"], "team_name": team["name"]}
        return response("ok", data, [{"ref_type": "task_grant", "ref_id": task_id,
                                       "ref_version": str(grant.snapshot_date),
                                       "content_sha256": canonical_hash(data)}])

    @staticmethod
    def _edge(edge: dict[str, Any]) -> dict[str, Any]:
        return {
            "member_a": edge["member_a_person_id"], "member_b": edge["member_b_person_id"],
            "relationship_type": edge["relationship_type"], "valence": edge["valence"],
            "salience": edge["salience"], "summary": edge["summary"], "risk": edge["risk"],
        }

    @staticmethod
    def _descendants(units: list[dict[str, Any]], root_unit_id: str) -> set[str]:
        children: dict[str | None, list[str]] = {}
        for unit in units:
            children.setdefault(unit["parent_unit_id"], []).append(unit["unit_id"])
        descendants = {root_unit_id}
        pending = [root_unit_id]
        while pending:
            parent = pending.pop()
            for child in children.get(parent, []):
                if child not in descendants:
                    descendants.add(child)
                    pending.append(child)
        return descendants

    def read_organization_overview(self, **kwargs: str) -> dict[str, Any]:
        grant, denied = self.authorize(tool_name="read_organization_overview", **kwargs)
        if denied:
            return denied
        assert grant
        try:
            grant.assert_organization_scope()
        except AuthorizationError as error:
            return response("access_denied", missing_information=[str(error)])
        try:
            organization = self.repository.organization(grant.organization_id, grant.snapshot_date)
            units = self.repository.units(grant.organization_id, grant.snapshot_date)
            people = self.repository.people(grant.organization_id, grant.snapshot_date)
            availability = self.repository.overview_availability(grant.organization_id, grant.snapshot_date)
            relationship_snapshot = self.repository.relationship_snapshot(grant.organization_id, grant.snapshot_date)
        except NotFoundError:
            return response("not_found")
        data = {
            "organization_id": organization["organization_id"], "snapshot_date": organization["snapshot_date"],
            "unit_ids": [unit["unit_id"] for unit in units], "person_count": len(people),
            "available_data": {
                "person_profiles": availability["person_profiles"], "person_models": availability["person_models"],
                "relationship_snapshot_id": relationship_snapshot["relationship_snapshot_id"] if relationship_snapshot else None,
                "team_models": any((availability["team_role_ecology_assessments"], availability["team_health_assessments"], availability["collaboration_structure_diagnoses"])),
                "team_role_ecology_assessments": availability["team_role_ecology_assessments"],
                "team_health_assessments": availability["team_health_assessments"],
                "collaboration_structure_diagnoses": availability["collaboration_structure_diagnoses"], "projects": availability["projects"],
            },
        }
        return response("ok", data, [{"ref_type": "organization_snapshot", "ref_id": grant.organization_id,
                                        "ref_version": str(grant.snapshot_date), "content_sha256": canonical_hash(organization)}])

    def unavailable_team_result(self, *, tool_name: str, team_id: str,
                                result_id: str | None = None, **kwargs: str) -> dict[str, Any]:
        """Check team scope before reporting that no accepted result exists."""

        grant, denied = self.authorize(tool_name=tool_name, **kwargs)
        if denied:
            return denied
        assert grant
        try:
            grant.assert_unit(team_id)
            units = self.repository.units(grant.organization_id, grant.snapshot_date)
        except AuthorizationError as error:
            return response("access_denied", missing_information=[str(error)])
        except NotFoundError:
            return response("not_found")
        if team_id not in {unit["unit_id"] for unit in units}:
            return response("input_invalid", missing_information=["team_id 不是当前快照的正式 unit_id"])
        if result_id is not None:
            return response("not_found", missing_information=["result_id 不存在或不属于当前范围"])
        return response("data_not_available", missing_information=["当前快照尚无该对象的已保存数据"])

    def unavailable_scope_result(self, *, tool_name: str, scope_id: str,
                                 result_id: str | None = None, **kwargs: str) -> dict[str, Any]:
        """Check an organization or unit scope before reporting absent diagnostics."""

        grant, denied = self.authorize(tool_name=tool_name, **kwargs)
        if denied:
            return denied
        assert grant
        try:
            if scope_id == grant.organization_id:
                grant.assert_organization_scope()
            else:
                grant.assert_unit(scope_id)
                units = self.repository.units(grant.organization_id, grant.snapshot_date)
                if scope_id not in {unit["unit_id"] for unit in units}:
                    return response("input_invalid", missing_information=["scope_id 不是当前快照的正式范围"])
        except AuthorizationError as error:
            return response("access_denied", missing_information=[str(error)])
        except NotFoundError:
            return response("not_found")
        if result_id is not None:
            return response("not_found", missing_information=["result_id 不存在或不属于当前范围"])
        return response("data_not_available", missing_information=["当前快照尚无该对象的已保存数据"])

    def unavailable_project_result(self, *, tool_name: str, project_id: str,
                                   result_id: str | None = None, **kwargs: str) -> dict[str, Any]:
        """Check project scope before reporting that the current baseline has no project data."""

        grant, denied = self.authorize(tool_name=tool_name, **kwargs)
        if denied:
            return denied
        assert grant
        try:
            grant.assert_project(project_id)
        except AuthorizationError as error:
            return response("access_denied", missing_information=[str(error)])
        if not self.repository.project_exists(grant.organization_id, grant.snapshot_date, project_id):
            return response("not_found")
        if result_id is not None:
            return response("not_found", missing_information=["result_id 不存在或不属于当前项目"])
        return response("data_not_available", missing_information=["当前快照尚无该对象的已保存数据"])

    def read_organization_structure(self, *, scope_id: str | None = None,
                                    include_descendant_units: bool = True, **kwargs: str) -> dict[str, Any]:
        grant, denied = self.authorize(tool_name="read_organization_structure", **kwargs)
        if denied:
            return denied
        assert grant
        selected_scope = scope_id or grant.organization_id
        if selected_scope == grant.organization_id:
            try:
                grant.assert_organization_scope()
            except AuthorizationError as error:
                return response("access_denied", missing_information=[str(error)])
        else:
            try:
                grant.assert_unit(selected_scope)
            except AuthorizationError as error:
                return response("access_denied", missing_information=[str(error)])
        try:
            organization = self.repository.organization(grant.organization_id, grant.snapshot_date)
            units = self.repository.units(grant.organization_id, grant.snapshot_date)
        except NotFoundError:
            return response("not_found")
        if selected_scope == grant.organization_id:
            selected_units = {unit["unit_id"] for unit in units}
        elif selected_scope in {unit["unit_id"] for unit in units}:
            selected_units = self._descendants(units, selected_scope) if include_descendant_units else {selected_scope}
        else:
            return response("input_invalid", missing_information=["scope_id 不是当前快照的 organization_id 或 unit_id"])
        if not selected_units.issubset(grant.allowed_unit_ids):
            return response("access_denied", missing_information=["Task 未授权该组织范围内的全部组织单元"])
        try:
            people = self.repository.people(grant.organization_id, grant.snapshot_date)
        except NotFoundError:
            return response("not_found")
        selected_people = [person for person in people if person["unit_id"] in selected_units]
        if not {person["person_id"] for person in selected_people}.issubset(grant.allowed_person_ids):
            return response("access_denied", missing_information=["Task 未授权该组织范围内的全部成员"])
        data = {"organization": organization, "scope_id": selected_scope,
                "units": [unit for unit in units if unit["unit_id"] in selected_units], "people": selected_people}
        return response("ok", data, [{"ref_type": "organization_snapshot", "ref_id": grant.organization_id,
                                        "ref_version": str(grant.snapshot_date), "content_sha256": canonical_hash(data)}])

    def read_person_profile(self, *, person_id: str, **kwargs: str) -> dict[str, Any]:
        grant, denied = self.authorize(tool_name="read_person_profile", **kwargs)
        if denied:
            return denied
        assert grant
        try:
            grant.assert_person(person_id)
            row = self.repository.person_profile(grant.organization_id, grant.snapshot_date, person_id)
        except AuthorizationError as error:
            return response("access_denied", missing_information=[str(error)])
        except NotFoundError:
            return response("not_found")
        profile = dict(row["profile_json"])
        for field in ("person_id", "name", "department", "position"):
            profile.pop(field, None)
        data = {"person_id": person_id, "formal_position": {
            "name": row["name"], "formal_title": row["formal_title"], "unit_id": row["unit_id"],
            "formal_manager_person_id": row["formal_manager_person_id"], "functional_manager": row["functional_manager"],
            "employment_type": row["employment_type"], "formal_structure_note": row["formal_structure_note"],
        }, "profile": profile}
        return response("ok", data, [{"ref_type": "person_profile", "ref_id": person_id,
                                        "ref_version": str(grant.snapshot_date), "content_sha256": canonical_hash(row["profile_json"])}])

    def read_person_model(self, *, person_id: str, model_version: int | None = None, **kwargs: str) -> dict[str, Any]:
        grant, denied = self.authorize(tool_name="read_person_model", **kwargs)
        if denied:
            return denied
        assert grant
        try:
            grant.assert_person(person_id)
            row = self.repository.person_model(grant.organization_id, grant.snapshot_date, person_id, model_version)
            markdown = self.repository.model_markdown(row["relative_path"])
        except AuthorizationError as error:
            return response("access_denied", missing_information=[str(error)])
        except (ModelDocumentUnavailableError, ValueError):
            return response("data_not_available", missing_information=["人物模型 Markdown 文件状态无效"])
        except NotFoundError:
            return response("not_found")
        data = {"person_id": person_id, "model": {"model_document_id": row["model_document_id"],
                "model_version": row["model_version"], "model_status": row["model_status"],
                "markdown": markdown, "model_json": row["model_json"]}}
        return response("ok", data, [{"ref_type": "person_model", "ref_id": row["model_document_id"],
                                        "ref_version": str(row["model_version"]),
                                        "content_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest()}])

    def read_person_collaboration_relations(self, *, person_id: str,
                                            counterparty_person_ids: list[str] | None = None, **kwargs: str) -> dict[str, Any]:
        grant, denied = self.authorize(tool_name="read_person_collaboration_relations", **kwargs)
        if denied:
            return denied
        assert grant
        requested_counterparties = set(counterparty_person_ids or [])
        try:
            grant.assert_person(person_id)
            for counterparty in requested_counterparties:
                grant.assert_person(counterparty)
            snapshot, edges = self.repository.relationships(grant.organization_id, grant.snapshot_date)
        except AuthorizationError as error:
            return response("access_denied", missing_information=[str(error)])
        except NotFoundError:
            return response("not_found")
        selected = [edge for edge in edges if person_id in (edge["member_a_person_id"], edge["member_b_person_id"])]
        if requested_counterparties:
            selected = [edge for edge in selected if ({edge["member_a_person_id"], edge["member_b_person_id"]} - {person_id}).issubset(requested_counterparties)]
        elif len(grant.allowed_person_ids) > 1:
            selected = [edge for edge in selected if ({edge["member_a_person_id"], edge["member_b_person_id"]} - {person_id}).issubset(grant.allowed_person_ids)]
        data = {"relationship_snapshot": {"relationship_snapshot_id": snapshot["relationship_snapshot_id"], "status": snapshot["status"]},
                "person_id": person_id, "relations": [self._edge(edge) for edge in selected]}
        return response("ok", data, [{"ref_type": "relationship_snapshot", "ref_id": snapshot["relationship_snapshot_id"],
                                        "ref_version": str(grant.snapshot_date), "content_sha256": canonical_hash(selected)}])

    def read_team_members(self, *, team_id: str, include_descendant_units: bool = False, **kwargs: str) -> dict[str, Any]:
        grant, denied = self.authorize(tool_name="read_team_members", **kwargs)
        if denied:
            return denied
        assert grant
        try:
            grant.assert_unit(team_id)
            units = self.repository.units(grant.organization_id, grant.snapshot_date)
            people = self.repository.people(grant.organization_id, grant.snapshot_date)
        except AuthorizationError as error:
            return response("access_denied", missing_information=[str(error)])
        unit = next((unit for unit in units if unit["unit_id"] == team_id), None)
        if not unit:
            return response("input_invalid", missing_information=["team_id 不是当前快照的正式 unit_id"])
        team_units = self._descendants(units, team_id) if include_descendant_units else {team_id}
        if not team_units.issubset(grant.allowed_unit_ids):
            return response("access_denied", missing_information=["Task 未授权该团队范围内的全部组织单元"])
        members = [person for person in people if person["unit_id"] in team_units]
        if not {person["person_id"] for person in members}.issubset(grant.allowed_person_ids):
            return response("access_denied", missing_information=["Task 未授权该团队范围内的全部成员"])
        data = {"team": {"team_id": unit["unit_id"], "name": unit["name"],
                "manager_person_id": unit["manager_person_id"], "parent_unit_id": unit["parent_unit_id"]},
                "member_ids": [person["person_id"] for person in members], "members": members}
        return response("ok", data, [{"ref_type": "organization_unit", "ref_id": team_id,
                                        "ref_version": str(grant.snapshot_date), "content_sha256": canonical_hash(data)}])

    def read_team_collaboration_relations(self, *, team_id: str, relation_scope: str = "all",
                                          include_descendant_units: bool = False, **kwargs: str) -> dict[str, Any]:
        grant, denied = self.authorize(tool_name="read_team_collaboration_relations", **kwargs)
        if denied:
            return denied
        assert grant
        if relation_scope not in {"internal", "cross_team", "all"}:
            return response("input_invalid", missing_information=["relation_scope 必须是 internal、cross_team 或 all"])
        try:
            grant.assert_unit(team_id)
            units = self.repository.units(grant.organization_id, grant.snapshot_date)
            people = self.repository.people(grant.organization_id, grant.snapshot_date)
            snapshot, edges = self.repository.relationships(grant.organization_id, grant.snapshot_date)
        except AuthorizationError as error:
            return response("access_denied", missing_information=[str(error)])
        except NotFoundError:
            return response("not_found")
        if team_id not in {unit["unit_id"] for unit in units}:
            return response("input_invalid", missing_information=["team_id 不是当前快照的正式 unit_id"])
        team_units = self._descendants(units, team_id) if include_descendant_units else {team_id}
        if not team_units.issubset(grant.allowed_unit_ids):
            return response("access_denied", missing_information=["Task 未授权该团队范围内的全部组织单元"])
        member_ids = {person["person_id"] for person in people if person["unit_id"] in team_units}
        if not member_ids.issubset(grant.allowed_person_ids):
            return response("access_denied", missing_information=["Task 未授权该团队范围内的全部成员"])
        internal = [edge for edge in edges if edge["member_a_person_id"] in member_ids and edge["member_b_person_id"] in member_ids]
        cross = [edge for edge in edges if (edge["member_a_person_id"] in member_ids) ^ (edge["member_b_person_id"] in member_ids)]
        all_selected = internal + cross
        allowed_edges = [edge for edge in all_selected if {
            edge["member_a_person_id"], edge["member_b_person_id"]
        }.issubset(grant.allowed_person_ids)]
        allowed_internal = [edge for edge in allowed_edges if edge in internal]
        allowed_cross = [edge for edge in allowed_edges if edge in cross]
        returned_edges = (
            allowed_internal if relation_scope == "internal"
            else allowed_cross if relation_scope == "cross_team"
            else allowed_internal + allowed_cross
        )
        data = {"team_id": team_id, "relationship_snapshot": {"relationship_snapshot_id": snapshot["relationship_snapshot_id"], "status": snapshot["status"]},
                "member_ids": sorted(member_ids),
                "internal_relations": [self._edge(edge) for edge in allowed_internal] if relation_scope in {"internal", "all"} else [],
                "cross_team_relations": [self._edge(edge) for edge in allowed_cross] if relation_scope in {"cross_team", "all"} else []}
        return response("ok", data, [{"ref_type": "relationship_snapshot", "ref_id": snapshot["relationship_snapshot_id"],
                                        "ref_version": str(grant.snapshot_date), "content_sha256": canonical_hash(returned_edges)}])
