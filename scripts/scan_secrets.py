"""Redacted history + tracked/unignored working-source scan, excluding artifacts."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = root / ".runtime/acceptance/safe-artifacts"
output.mkdir(parents=True, exist_ok=True)
scanner = "ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f"


def scan(mode, folder, target):
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-e",
            "GIT_CONFIG_COUNT=1",
            "-e",
            "GIT_CONFIG_KEY_0=safe.directory",
            "-e",
            "GIT_CONFIG_VALUE_0=/repo",
            "-v",
            str(folder) + ":/repo:ro",
            "-v",
            str(output) + ":/reports",
            scanner,
            mode,
            "/repo",
            "--redact=100",
            "--report-format=json",
            "--report-path=/reports/" + target,
        ],
        check=True,
    )


scan("git", root, "gitleaks-history.json")
paths = (
    subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
    )
    .decode()
    .split("\0")
)
with tempfile.TemporaryDirectory(prefix="jazsem-secret-scan-") as temporary:
    folder = Path(temporary)
    for name in paths:
        source = root / name
        if not name or not source.is_file():
            continue
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    scan("dir", folder, "gitleaks-working-tree.json")
print(json.dumps({"redacted_history_and_working_tree": "passed", "scanner": scanner}))
