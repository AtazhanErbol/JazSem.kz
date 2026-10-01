"""Kill/restart only the fixed synthetic Compose project; never accepts a target."""

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
checks = []


def command(args, timeout=180):
    result = subprocess.run(
        [*compose, *args], capture_output=True, text=True, timeout=timeout, check=False
    )
    if result.returncode:
        # Only the final exception type/line; never export arbitrary service logs.
        lines = result.stderr.strip().splitlines()
        raise RuntimeError(
            "Synthetic phase failed: "
            + (lines[-1] if lines else str(result.returncode))
        )
    return result.stdout


def phase(name):
    result = command(
        ["exec", "-T", "mail", "python", "/acceptance/acceptance_fault_state.py", name]
    )
    data = json.loads(result.strip().splitlines()[-1])
    checks.append(data)
    print(json.dumps(data), flush=True)


try:
    for kind in ("before", "after"):
        phase("start-" + kind)
        command(["kill", "-s", "SIGKILL", "heavy"])
        command(["start", "heavy"])
        phase("finish-" + kind)
    for kind in ("cancel", "timeout"):
        phase("start-" + kind)
        phase("finish-" + kind)
    phase("start-broker")
    command(["stop", "-t", "2", "short", "beat"])
    phase("enqueue-broker")
    command(["stop", "-t", "2", "redis"])
    phase("broker-down")
    command(["start", "redis", "short", "beat"])
    phase("finish-broker")
    command(["stop", "-t", "2", "short", "beat"])
    phase("prepare-extraction")
    command(["stop", "-t", "2", "minio"])
    command(["start", "short", "beat"])
    phase("failed-extraction")
    command(["start", "minio"])
    phase("finish-extraction")
    phase("smtp")
finally:
    command(["start", "redis", "minio", "short", "heavy", "beat"])
    output = root / ".runtime/acceptance/safe-artifacts/runtime-faults.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "checks": checks,
                "synthetic": True,
                "source_ref": os.environ.get("RC_SOURCE_REF", "working tree"),
            },
            indent=2,
        )
    )
