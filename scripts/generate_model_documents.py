#!/usr/bin/env python3
"""Generate readable person-model Markdown documents from PostgreSQL JSON."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = "postgresql://localhost/orgsight_demo"

QUERY = """
SELECT md.model_document_id, md.relative_path, p.name, p.formal_title, u.name AS unit_name,
       pm.model_json::text
FROM person_models pm
JOIN model_documents md ON md.model_document_id = pm.model_document_id
JOIN people p ON p.organization_id = pm.organization_id
  AND p.snapshot_date = pm.snapshot_date AND p.person_id = pm.person_id
JOIN organization_units u ON u.organization_id = p.organization_id
  AND u.snapshot_date = p.snapshot_date AND u.unit_id = p.unit_id
ORDER BY p.person_id;
"""


def bullet_lines(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def render_document(name: str, formal_title: str, unit_name: str, model: dict) -> str:
    big_five = model["big_five"]
    mbti = model["mbti"]
    enneagram = model["enneagram"]
    dark = model["dark_traits"]
    workplace = model["workplace_dynamics"]
    return f"""# {name}｜人物职业模型

## 职业定位

- 正式岗位：{formal_title}
- 所属单元：{unit_name}

## 专业优势

{bullet_lines(model['professional_strengths'])}

## 大五人格倾向

- 开放性：{big_five['openness']}
- 尽责性：{big_five['conscientiousness']}
- 外向性：{big_five['extraversion']}
- 宜人性：{big_five['agreeableness']}
- 情绪稳定性：{big_five['emotional_stability']}
- 判断依据：{big_five['reasoning']}

## 类型模型

- MBTI：{mbti['type']}（置信度 {mbti['confidence']:.2f}）
- MBTI 依据：{mbti['reasoning']}
- 九型人格：{enneagram['type']}（置信度 {enneagram['confidence']:.2f}）
- 九型依据：{enneagram['reasoning']}

## 阴暗人格倾向

- 自恋倾向：{dark['narcissism']['level']}（置信度 {dark['narcissism']['confidence']:.2f}）；{dark['narcissism']['reasoning']}
- 马基雅维利倾向：{dark['machiavellianism']['level']}（置信度 {dark['machiavellianism']['confidence']:.2f}）；{dark['machiavellianism']['reasoning']}
- 精神病态倾向：{dark['psychopathy']['level']}（置信度 {dark['psychopathy']['confidence']:.2f}）；{dark['psychopathy']['reasoning']}

## 核心动机与防御

### 核心恐惧

{bullet_lines(model['core_fears'])}

### 核心渴望

{bullet_lines(model['core_desires'])}

### 防御机制

{bullet_lines(model['defense_mechanisms'])}

## 工作与协作方式

- 工作方式：{workplace['work_style']}
- 沟通方式：{workplace['communication_style']}
- 决策方式：{workplace['decision_making_style']}
- 压力反应：{workplace['stress_response']}
- 冲突方式：{workplace['conflict_style']}
- 权力动态：{workplace['power_dynamics']}
- 信任建立：{workplace['trust_building']}
- 边界风格：{workplace['boundary_style']}

## 关系动态

{model['relationship_dynamics']}

## 综合侧写

{model['summary_profile']}
"""


def update_document_metadata(database: str, document_id: str, sha256: str) -> None:
    statement = (
        "UPDATE model_documents SET content_sha256 = '" + sha256 +
        "', document_status = 'generated', generated_at = now() WHERE model_document_id = '" +
        document_id.replace("'", "''") + "';"
    )
    subprocess.run(["psql", database, "--set", "ON_ERROR_STOP=1", "--quiet"], input=statement, text=True, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=DEFAULT_DATABASE_URL, help="PostgreSQL URL")
    args = parser.parse_args()
    query = subprocess.run(
        # --csv already selects an aligned, quoted CSV format. Combining it with
        # --no-align drops quoting and breaks JSON fields containing commas.
        ["psql", args.database, "--csv", "--tuples-only", "--set", "ON_ERROR_STOP=1", "--command", QUERY],
        check=True,
        capture_output=True,
        text=True,
    )
    rows = list(csv.reader(io.StringIO(query.stdout)))
    if len(rows) != 22:
        raise RuntimeError(f"预期从数据库读取 22 份人物模型，实际为 {len(rows)} 份")
    for document_id, relative_path, name, formal_title, unit_name, model_json in rows:
        destination = REPOSITORY_ROOT / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        content = render_document(name, formal_title, unit_name, json.loads(model_json))
        destination.write_text(content, encoding="utf-8")
        update_document_metadata(args.database, document_id, hashlib.sha256(content.encode("utf-8")).hexdigest())
    print(f"已从 PostgreSQL 生成 {len(rows)} 份人物模型 Markdown 文档。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
