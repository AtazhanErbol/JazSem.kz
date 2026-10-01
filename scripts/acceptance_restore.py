"""Consistent synthetic PostgreSQL + private-object restore, never production."""

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compose = [
    "docker",
    "compose",
    "-f",
    str(root / "infra/compose.acceptance.yml"),
    "-f",
    str(root / "infra/compose.acceptance-ai.yml"),
]
checks = []


def run(args, **kwargs):
    return subprocess.run([*compose, *args], check=True, **kwargs)


def phase(name, restored=False):
    env = ["-e", "DJANGO_SETTINGS_MODULE=config.settings.production"]
    if restored:
        env += [
            "-e",
            "DATABASE_URL=postgresql://acceptance:synthetic-only@postgres/jazsem_rc_restore",
            "-e",
            "S3_BUCKET=jazsem-acceptance-restored",
        ]
    result = run(
        [
            "exec",
            "-T",
            *env,
            "mail",
            "python",
            "/acceptance/acceptance_restore_state.py",
            name,
        ],
        capture_output=True,
        text=True,
    )
    check = json.loads(result.stdout.strip().splitlines()[-1])
    checks.append(check)
    print(json.dumps(check), flush=True)


started = time.monotonic()
try:
    run(["stop", "-t", "3", "backend", "short", "heavy", "beat"], capture_output=True)
    phase("seed")
    backup = root / ".runtime/acceptance/database.dump"
    with backup.open("wb") as stream:
        run(
            [
                "exec",
                "-T",
                "postgres",
                "pg_dump",
                "-U",
                "acceptance",
                "-d",
                "jazsem_rc_runtime",
                "-Fc",
            ],
            stdout=stream,
        )
    backup_done = time.monotonic()
    run(["exec", "-T", "postgres", "createdb", "-U", "acceptance", "jazsem_rc_restore"])
    with backup.open("rb") as stream:
        run(
            [
                "exec",
                "-T",
                "postgres",
                "pg_restore",
                "-U",
                "acceptance",
                "--no-owner",
                "--exit-on-error",
                "-d",
                "jazsem_rc_restore",
            ],
            stdin=stream,
        )
    phase("objects", restored=True)
    phase("verify", restored=True)
    report = {
        "source_ref": os.environ.get("RC_SOURCE_REF", "working tree"),
        "checks": checks,
        "dump_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
        "dump_bytes": backup.stat().st_size,
        "backup_seconds": round(backup_done - started, 2),
        "restore_and_verify_seconds": round(time.monotonic() - backup_done, 2),
        "rpo": "quiesced synthetic DB and matching objects; no writes during snapshot",
        "rto": "measured local restore/verification only; not a production SLA",
        "keys": "same isolated synthetic key restored through environment; no secret output",
    }
    (root / ".runtime/acceptance/safe-artifacts/restore.json").write_text(
        json.dumps(report, indent=2)
    )
finally:
    run(["start", "backend", "short", "heavy", "beat"], capture_output=True)
