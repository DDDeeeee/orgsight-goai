#!/usr/bin/env python3
"""Register an AgentTeams Leader credential in the independent GOAI database.

The credential is read from stdin and only its SHA-256 is stored. The command
does not print, persist, or send the plaintext token anywhere.
"""

from __future__ import annotations

import argparse
import os
import sys

import psycopg

from profilemesh_goai.authorization import token_sha256


ALLOWED_WORKER_IDS = (
    "talent-role-insight-lead",
    "role-and-position-analysis-worker",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--worker-id",
        default="talent-role-insight-lead",
        choices=ALLOWED_WORKER_IDS,
        help="仅允许登记当前最小演示链路中的已部署 AgentTeams 身份",
    )
    args = parser.parse_args()
    token = sys.stdin.read().strip()
    if not token:
        parser.error("通过 stdin 提供 AgentTeams Gateway 凭证")
    database_url = os.environ.get("PROFILEMESH_GOAI_DATABASE_URL", "postgresql://localhost/profilemesh_goai_demo")
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO mcp_worker_credentials
                 (credential_id, worker_id, token_sha256, status)
               VALUES (%s, %s, %s, 'active')
               ON CONFLICT (worker_id) DO UPDATE
                 SET token_sha256 = EXCLUDED.token_sha256,
                     status = 'active', expires_at = NULL""",
            (f"agentteams-{args.worker_id}", args.worker_id, token_sha256(token)),
        )
    print(f"registered {args.worker_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
