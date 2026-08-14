#!/usr/bin/env python3
"""Load reviewed organization data into an isolated local PostgreSQL database."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIRECTORY = REPOSITORY_ROOT / "fixtures" / "demo-office"
DEFAULT_DATABASE_URL = "postgresql://localhost/orgsight_demo"


def sql_text(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def sql_json(value: object) -> str:
    return sql_text(json.dumps(value, ensure_ascii=False, separators=(",", ":"))) + "::jsonb"


def read_json(name: str) -> dict:
    with (FIXTURE_DIRECTORY / name).open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def document_id_for(person_id: str, snapshot_date: str) -> str:
    return f"person-{person_id.removeprefix('p_')}-{snapshot_date}-v1"


def stable_json_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate(organization: dict, profiles: dict, models: dict, relationships: dict) -> None:
    people_ids = {person["person_id"] for person in organization["people"]}
    profile_ids = {profile["person_id"] for profile in profiles["profiles"]}
    model_ids = {model["person_id"] for model in models["models"]}
    relationship_pairs: set[tuple[str, str]] = set()

    if len(people_ids) != organization["member_count"]:
        raise ValueError("组织成员数与唯一 person_id 数不一致")
    if people_ids != profile_ids or people_ids != model_ids:
        raise ValueError("组织、档案和模型的 person_id 集合不一致")
    for edge in relationships["relationships"]:
        member_a = edge["member_a"]
        member_b = edge["member_b"]
        if member_a not in people_ids or member_b not in people_ids or member_a == member_b:
            raise ValueError("关系快照包含未定义或重复的人员端点")
        pair = tuple(sorted((member_a, member_b)))
        if pair in relationship_pairs:
            raise ValueError("关系快照包含重复成员对")
        relationship_pairs.add(pair)
        if edge["valence"] not in {"positive", "neutral", "negative"}:
            raise ValueError("关系倾向必须是 positive、neutral 或 negative")
        if not 1 <= edge["salience"] <= 5:
            raise ValueError("关系显著度必须是 1-5")
def build_seed_sql(organization: dict, profiles: dict, models: dict, relationships: dict) -> str:
    organization_id = organization["organization_id"]
    snapshot_date = organization["snapshot_date"]
    statements = ["BEGIN;"]
    statements.append(
        """INSERT INTO organization_snapshots
        (organization_id, snapshot_date, display_name, scope, status)
        VALUES ({}, {}, {}, {}, 'active')
        ON CONFLICT (organization_id, snapshot_date) DO UPDATE SET
          display_name = EXCLUDED.display_name,
          scope = EXCLUDED.scope,
          status = EXCLUDED.status;""".format(
            sql_text(organization_id), sql_text(snapshot_date), sql_text(organization["display_name"]),
            sql_text(organization["scope"])
        )
    )
    for unit in organization["units"]:
        statements.append(
            """INSERT INTO organization_units
            (organization_id, snapshot_date, unit_id, name, parent_unit_id, manager_person_id)
            VALUES ({}, {}, {}, {}, {}, {})
            ON CONFLICT (organization_id, snapshot_date, unit_id) DO UPDATE SET
              name = EXCLUDED.name, parent_unit_id = EXCLUDED.parent_unit_id,
              manager_person_id = EXCLUDED.manager_person_id;""".format(
                sql_text(organization_id), sql_text(snapshot_date), sql_text(unit["unit_id"]),
                sql_text(unit["name"]), sql_text(unit["parent_unit_id"]), sql_text(unit["manager_person_id"])
            )
        )
    for person in organization["people"]:
        statements.append(
            """INSERT INTO people
            (organization_id, snapshot_date, person_id, name, formal_title, unit_id,
             formal_manager_person_id, functional_manager, employment_type, formal_structure_note)
            VALUES ({}, {}, {}, {}, {}, {}, {}, {}, {}, {})
            ON CONFLICT (organization_id, snapshot_date, person_id) DO UPDATE SET
              name = EXCLUDED.name, formal_title = EXCLUDED.formal_title, unit_id = EXCLUDED.unit_id,
              formal_manager_person_id = EXCLUDED.formal_manager_person_id,
              functional_manager = EXCLUDED.functional_manager,
              employment_type = EXCLUDED.employment_type,
              formal_structure_note = EXCLUDED.formal_structure_note;""".format(
                sql_text(organization_id), sql_text(snapshot_date), sql_text(person["person_id"]),
                sql_text(person["name"]), sql_text(person["formal_title"]), sql_text(person["unit_id"]),
                sql_text(person.get("formal_manager_person_id")), sql_text(person.get("functional_manager")),
                sql_text(person["employment_type"]), sql_text(person.get("formal_structure_note"))
            )
        )
    for profile in profiles["profiles"]:
        statements.append(
            """INSERT INTO person_profiles
            (organization_id, snapshot_date, person_id, profile_json, source_status)
            VALUES ({}, {}, {}, {}, {})
            ON CONFLICT (organization_id, snapshot_date, person_id) DO UPDATE SET
              profile_json = EXCLUDED.profile_json, source_status = EXCLUDED.source_status;""".format(
                sql_text(organization_id), sql_text(snapshot_date), sql_text(profile["person_id"]),
                sql_json(profile), sql_text(profiles["status"])
            )
        )
    for model in models["models"]:
        document_id = document_id_for(model["person_id"], snapshot_date)
        relative_path = f"data/model-documents/{document_id}.md"
        statements.append(
            """INSERT INTO model_documents
            (model_document_id, organization_id, snapshot_date, subject_type, subject_id, model_type,
             relative_path, source_json_sha256, document_status)
            VALUES ({}, {}, {}, 'person', {}, 'person_model', {}, {}, 'pending_generation')
            ON CONFLICT (model_document_id) DO UPDATE SET
              relative_path = EXCLUDED.relative_path,
              source_json_sha256 = EXCLUDED.source_json_sha256,
              document_status = 'pending_generation';""".format(
                sql_text(document_id), sql_text(organization_id), sql_text(snapshot_date),
                sql_text(model["person_id"]), sql_text(relative_path), sql_text(stable_json_sha256(model))
            )
        )
        statements.append(
            """INSERT INTO person_models
            (organization_id, snapshot_date, person_id, model_version, model_document_id, model_json, model_status)
            VALUES ({}, {}, {}, 1, {}, {}, 'active')
            ON CONFLICT (organization_id, snapshot_date, person_id, model_version) DO UPDATE SET
              model_document_id = EXCLUDED.model_document_id, model_json = EXCLUDED.model_json,
              model_status = EXCLUDED.model_status;""".format(
                sql_text(organization_id), sql_text(snapshot_date), sql_text(model["person_id"]),
                sql_text(document_id), sql_json(model)
            )
        )
    statements.append(
        """INSERT INTO relationship_snapshots
        (relationship_snapshot_id, organization_id, snapshot_date, status, usage_note)
        VALUES ({}, {}, {}, {}, {})
        ON CONFLICT (relationship_snapshot_id) DO UPDATE SET
          status = EXCLUDED.status, usage_note = EXCLUDED.usage_note;""".format(
            sql_text(relationships["snapshot_id"]), sql_text(organization_id), sql_text(snapshot_date),
            sql_text(relationships["status"]), sql_text(relationships["usage_note"])
        )
    )
    statements.append("DELETE FROM relationship_edges WHERE relationship_snapshot_id = {};".format(sql_text(relationships["snapshot_id"])))
    for index, edge in enumerate(relationships["relationships"], start=1):
        statements.append(
            """INSERT INTO relationship_edges
            (relationship_snapshot_id, relationship_index, member_a_person_id, member_b_person_id,
             relationship_type, valence, salience, summary, risk)
            VALUES ({}, {}, {}, {}, {}, {}, {}, {}, {});""".format(
                sql_text(relationships["snapshot_id"]), index, sql_text(edge["member_a"]), sql_text(edge["member_b"]),
                sql_text(edge["relationship_type"]), sql_text(edge["valence"]), edge["salience"],
                sql_text(edge["summary"]), sql_text(edge["risk"])
            )
        )
    statements.append("COMMIT;")
    return "\n".join(statements)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=DEFAULT_DATABASE_URL, help="PostgreSQL URL")
    args = parser.parse_args()

    organization = read_json("organization_structure.json")
    profiles = read_json("person_profiles_seed.json")
    models = read_json("person_models_seed.json")
    relationships = read_json("relationship_snapshot_seed.json")
    validate(organization, profiles, models, relationships)

    result = subprocess.run(
        ["psql", args.database, "--set", "ON_ERROR_STOP=1", "--quiet"],
        input=build_seed_sql(organization, profiles, models, relationships),
        text=True,
        check=False,
    )
    if result.returncode:
        return result.returncode
    print("已导入：22 人、22 份档案、22 份人物模型和 63 条关系边。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
