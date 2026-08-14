"""PostgreSQL read repository for the seven currently available MCP tools."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
import os
from pathlib import Path
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from .authorization import TaskGrant, json_list, token_sha256
from psycopg.types.json import Jsonb


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MODEL_DOCUMENT_ROOT = (REPOSITORY_ROOT / "data" / "model-documents").resolve()


class NotFoundError(Exception):
    """Raised for an absent object while keeping read responses non-exceptional."""


class ModelDocumentUnavailableError(Exception):
    """Raised when a registered model document cannot be safely read."""


class PostgresRepository:
    """Only queries the independent GOAI PostgreSQL database."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.environ.get(
            "PROFILEMESH_GOAI_DATABASE_URL", "postgresql://localhost/profilemesh_goai_demo"
        )

    @contextmanager
    def _connection(self) -> Iterator[psycopg.Connection[Any]]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            yield connection

    @staticmethod
    def _one(cursor: Any) -> dict[str, Any]:
        row = cursor.fetchone()
        if row is None:
            raise NotFoundError
        return dict(row)

    def resolve_worker(self, bearer_token: str) -> str | None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT worker_id FROM mcp_worker_credentials
                WHERE token_sha256 = %s AND status = 'active'
                  AND (expires_at IS NULL OR expires_at > now())""",
                (token_sha256(bearer_token),),
            )
            row = cursor.fetchone()
            return row["worker_id"] if row else None

    def get_grant(self, task_id: str) -> TaskGrant | None:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT task_id, worker_id, organization_id, snapshot_date, task_objective,
                          allowed_tools, allowed_person_ids, allowed_unit_ids,
                          allowed_project_ids, status, expires_at
                   FROM mcp_task_grants WHERE task_id = %s""",
                (task_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return TaskGrant(
                task_id=row["task_id"], worker_id=row["worker_id"],
                organization_id=row["organization_id"], snapshot_date=row["snapshot_date"],
                task_objective=row["task_objective"], allowed_tools=json_list(row["allowed_tools"]),
                allowed_person_ids=json_list(row["allowed_person_ids"]),
                allowed_unit_ids=json_list(row["allowed_unit_ids"]),
                allowed_project_ids=json_list(row["allowed_project_ids"]),
                status=row["status"], expires_at=row["expires_at"],
            )

    def upsert_task_grant(
        self, *, task_id: str, worker_id: str, organization_id: str, snapshot_date: date,
        task_objective: str, allowed_tools: frozenset[str], allowed_person_ids: frozenset[str],
        allowed_unit_ids: frozenset[str], allowed_project_ids: frozenset[str],
    ) -> TaskGrant:
        """Create one immutable active Grant, or accept an identical retry."""

        proposed = TaskGrant(
            task_id=task_id, worker_id=worker_id, organization_id=organization_id,
            snapshot_date=snapshot_date, task_objective=task_objective,
            allowed_tools=frozenset(allowed_tools), allowed_person_ids=frozenset(allowed_person_ids),
            allowed_unit_ids=frozenset(allowed_unit_ids), allowed_project_ids=frozenset(allowed_project_ids),
            status="active", expires_at=None,
        )
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT task_id, worker_id, organization_id, snapshot_date, task_objective,
                          allowed_tools, allowed_person_ids, allowed_unit_ids,
                          allowed_project_ids, status, expires_at
                   FROM mcp_task_grants WHERE task_id = %s FOR UPDATE""",
                (task_id,),
            )
            row = cursor.fetchone()
            if row:
                existing = TaskGrant(
                    task_id=row["task_id"], worker_id=row["worker_id"],
                    organization_id=row["organization_id"], snapshot_date=row["snapshot_date"],
                    task_objective=row["task_objective"], allowed_tools=json_list(row["allowed_tools"]),
                    allowed_person_ids=json_list(row["allowed_person_ids"]),
                    allowed_unit_ids=json_list(row["allowed_unit_ids"]),
                    allowed_project_ids=json_list(row["allowed_project_ids"]),
                    status=row["status"], expires_at=row["expires_at"],
                )
                immutable = (
                    existing.worker_id, existing.organization_id, existing.snapshot_date,
                    existing.allowed_tools, existing.allowed_person_ids, existing.allowed_unit_ids,
                    existing.allowed_project_ids,
                )
                expected = (
                    proposed.worker_id, proposed.organization_id, proposed.snapshot_date,
                    proposed.allowed_tools, proposed.allowed_person_ids, proposed.allowed_unit_ids,
                    proposed.allowed_project_ids,
                )
                if immutable != expected:
                    raise ValueError("同一 task_id 已登记不同的授权范围")
                if existing.status != "active":
                    raise ValueError("同一 task_id 的既有授权不可重新激活")
                return existing
            cursor.execute(
                """INSERT INTO mcp_task_grants (
                       task_id, worker_id, organization_id, snapshot_date, task_objective,
                       allowed_tools, allowed_person_ids, allowed_unit_ids, allowed_project_ids, status
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'active')""",
                (
                    proposed.task_id, proposed.worker_id, proposed.organization_id, proposed.snapshot_date,
                    proposed.task_objective, Jsonb(sorted(proposed.allowed_tools)),
                    Jsonb(sorted(proposed.allowed_person_ids)), Jsonb(sorted(proposed.allowed_unit_ids)),
                    Jsonb(sorted(proposed.allowed_project_ids)),
                ),
            )
        return proposed

    def organization(self, organization_id: str, snapshot_date: date) -> dict[str, Any]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT organization_id, snapshot_date::text, display_name, scope, status
                   FROM organization_snapshots WHERE organization_id = %s AND snapshot_date = %s""",
                (organization_id, snapshot_date),
            )
            return self._one(cursor)

    def units(self, organization_id: str, snapshot_date: date) -> list[dict[str, Any]]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT unit_id, name, parent_unit_id, manager_person_id
                   FROM organization_units WHERE organization_id = %s AND snapshot_date = %s ORDER BY unit_id""",
                (organization_id, snapshot_date),
            )
            return [dict(row) for row in cursor.fetchall()]

    def people(self, organization_id: str, snapshot_date: date) -> list[dict[str, Any]]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT person_id, name, formal_title, unit_id, formal_manager_person_id,
                          functional_manager, employment_type, formal_structure_note
                   FROM people WHERE organization_id = %s AND snapshot_date = %s ORDER BY person_id""",
                (organization_id, snapshot_date),
            )
            return [dict(row) for row in cursor.fetchall()]

    def person_by_name(self, name: str) -> dict[str, Any]:
        """Resolve one synthetic baseline person for controlled task setup."""

        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT organization_id, snapshot_date, person_id, name, unit_id
                   FROM people WHERE name = %s
                   ORDER BY snapshot_date DESC LIMIT 2""",
                (name,),
            )
            rows = [dict(row) for row in cursor.fetchall()]
        if len(rows) != 1:
            raise NotFoundError
        return rows[0]

    def person_profile(self, organization_id: str, snapshot_date: date, person_id: str) -> dict[str, Any]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT p.person_id, p.name, p.formal_title, p.unit_id,
                          p.formal_manager_person_id, p.functional_manager, p.employment_type,
                          p.formal_structure_note, pp.profile_json
                   FROM people p JOIN person_profiles pp
                     ON pp.organization_id = p.organization_id AND pp.snapshot_date = p.snapshot_date
                    AND pp.person_id = p.person_id
                   WHERE p.organization_id = %s AND p.snapshot_date = %s AND p.person_id = %s""",
                (organization_id, snapshot_date, person_id),
            )
            return self._one(cursor)

    def person_model(
        self, organization_id: str, snapshot_date: date, person_id: str, model_version: int | None
    ) -> dict[str, Any]:
        version_condition = "AND pm.model_version = %s" if model_version is not None else ""
        parameters: list[Any] = [organization_id, snapshot_date, person_id]
        if model_version is not None:
            parameters.append(model_version)
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""SELECT pm.model_document_id, pm.model_version, pm.model_status, pm.model_json,
                           md.relative_path, md.source_json_sha256, md.content_sha256
                    FROM person_models pm JOIN model_documents md
                      ON md.model_document_id = pm.model_document_id
                    WHERE pm.organization_id = %s AND pm.snapshot_date = %s AND pm.person_id = %s
                    {version_condition}
                    ORDER BY pm.model_version DESC LIMIT 1""",
                parameters,
            )
            return self._one(cursor)

    def relationships(self, organization_id: str, snapshot_date: date) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT relationship_snapshot_id, status, usage_note
                   FROM relationship_snapshots WHERE organization_id = %s AND snapshot_date = %s
                   ORDER BY relationship_snapshot_id DESC LIMIT 1""",
                (organization_id, snapshot_date),
            )
            snapshot = self._one(cursor)
            cursor.execute(
                """SELECT member_a_person_id, member_b_person_id, relationship_type, valence,
                          salience, summary, risk
                   FROM relationship_edges WHERE relationship_snapshot_id = %s
                   ORDER BY relationship_index""",
                (snapshot["relationship_snapshot_id"],),
            )
            return snapshot, [dict(row) for row in cursor.fetchall()]

    def relationship_snapshot(self, organization_id: str, snapshot_date: date) -> dict[str, Any] | None:
        """Return relationship metadata without treating its absence as an absent organization."""

        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT relationship_snapshot_id, status, usage_note
                   FROM relationship_snapshots WHERE organization_id = %s AND snapshot_date = %s
                   ORDER BY relationship_snapshot_id DESC LIMIT 1""",
                (organization_id, snapshot_date),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def project_exists(self, organization_id: str, snapshot_date: date, project_id: str) -> bool:
        """Check the raw project record before reporting its derived data as unavailable."""

        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT EXISTS(
                       SELECT 1 FROM projects
                       WHERE organization_id = %s AND snapshot_date = %s AND project_id = %s
                   ) AS exists""",
                (organization_id, snapshot_date, project_id),
            )
            return bool(self._one(cursor)["exists"])

    def model_markdown(self, relative_path: str) -> str:
        candidate = (REPOSITORY_ROOT / relative_path).resolve()
        if candidate.parent != MODEL_DOCUMENT_ROOT or candidate.suffix != ".md":
            raise ValueError("模型文档路径不在允许目录内")
        try:
            return candidate.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise ModelDocumentUnavailableError from error

    def overview_availability(self, organization_id: str, snapshot_date: date) -> dict[str, bool]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT
                  EXISTS(SELECT 1 FROM person_profiles WHERE organization_id = %s AND snapshot_date = %s) AS person_profiles,
                  EXISTS(SELECT 1 FROM person_models WHERE organization_id = %s AND snapshot_date = %s) AS person_models,
                  EXISTS(SELECT 1 FROM relationship_snapshots WHERE organization_id = %s AND snapshot_date = %s) AS relationships,
                  EXISTS(SELECT 1 FROM skill_results WHERE organization_id = %s AND snapshot_date = %s
                         AND status = 'accepted' AND result_type = 'team_role_ecology_assessment') AS team_role_ecology_assessments,
                  EXISTS(SELECT 1 FROM skill_results WHERE organization_id = %s AND snapshot_date = %s
                         AND status = 'accepted' AND result_type = 'team_health_assessment') AS team_health_assessments,
                  EXISTS(SELECT 1 FROM skill_results WHERE organization_id = %s AND snapshot_date = %s
                         AND status = 'accepted' AND result_type = 'collaboration_structure_diagnosis') AS collaboration_structure_diagnoses,
                  EXISTS(SELECT 1 FROM projects WHERE organization_id = %s AND snapshot_date = %s) AS projects""",
                (organization_id, snapshot_date) * 7,
            )
            return dict(self._one(cursor))
