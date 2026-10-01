"""Run and retain counts-only production startup/TLS/HTTP checks."""

import argparse
import json
import os
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("stage", choices=["init", "tls", "http"])
stage = parser.parse_args().stage
root = Path(__file__).resolve().parents[1]
result = subprocess.run(
    [
        "docker",
        "compose",
        "-f",
        str(root / "infra/compose.acceptance.yml"),
        "run",
        "--rm",
        "-e",
        "PYTHONPATH=/app",
        "mail",
        "python",
        "/acceptance/acceptance_runtime.py",
        stage,
    ],
    capture_output=True,
    text=True,
    check=True,
    timeout=180,
)
report = {
    "source_ref": os.environ.get("RC_SOURCE_REF", "working tree"),
    "checks": json.loads(result.stdout.strip().splitlines()[-1]),
}
output = root / ".runtime/acceptance/safe-artifacts"
output.mkdir(parents=True, exist_ok=True)
(output / f"runtime-{stage}.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report))
