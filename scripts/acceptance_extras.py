"""Persist heavy-queue and real private-S3 maintenance evidence safely."""

import json
import os
import subprocess
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


def run(args):
    result = subprocess.run(
        [*compose, *args], capture_output=True, text=True, timeout=180, check=False
    )
    if result.returncode:
        raise RuntimeError(
            "Synthetic extra acceptance phase failed; inspect private local stderr"
        )
    return result.stdout


checks = [
    json.loads(
        run(
            [
                "exec",
                "-T",
                "mail",
                "python",
                "/acceptance/acceptance_fault_state.py",
                "heavy-isolation",
            ]
        )
        .strip()
        .splitlines()[-1]
    )
]
try:
    run(["stop", "-t", "3", "backend", "short", "heavy", "beat"])
    checks.append(
        json.loads(
            run(
                [
                    "exec",
                    "-T",
                    "mail",
                    "python",
                    "/acceptance/acceptance_storage_cleanup.py",
                ]
            )
            .strip()
            .splitlines()[-1]
        )
    )
finally:
    run(["start", "backend", "short", "heavy", "beat"])
report = {
    "source_ref": os.environ.get("RC_SOURCE_REF", "working tree"),
    "checks": checks,
}
(root / ".runtime/acceptance/safe-artifacts/runtime-extras.json").write_text(
    json.dumps(report, indent=2)
)
print(json.dumps(report))
