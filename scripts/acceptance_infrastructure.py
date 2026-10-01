"""Real process outages on the fixed disposable acceptance Compose project.

No mocks, no production .env, no deletion; always restart interrupted services.
"""

import json
import os
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
compose = ["docker", "compose", "-f", str(root / "infra/compose.acceptance.yml")]
evidence = {
    "source_ref": os.environ.get("RC_SOURCE_REF", "working tree"),
    "checks": [],
    "containers": {},
}


def command(arguments, timeout=60):
    result = subprocess.run(
        arguments, capture_output=True, text=True, timeout=timeout, check=False
    )
    if result.returncode:
        # Do not relay arbitrary service error values or environment variables.
        raise RuntimeError("Acceptance command failed: " + " ".join(arguments[:4]))
    return result.stdout


def probe():
    output = command(
        [
            *compose,
            "exec",
            "-T",
            "-e",
            "PYTHONPATH=/app",
            "mail",
            "python",
            "/acceptance/acceptance_runtime.py",
            "probe",
        ],
        timeout=35,
    )
    return json.loads(output.strip().splitlines()[-1])


def wait_status(expected, seconds=95):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        state = probe()
        if state["ready"] == expected:
            return state
        time.sleep(3)
    raise AssertionError("Readiness did not reach the expected status")


for service in ("backend", "short", "heavy", "beat", "web"):
    container = command([*compose, "ps", "-q", service]).strip()
    data = json.loads(command(["docker", "inspect", container]))[0]
    assert data["Name"].startswith("/jazsem-acceptance-")
    assert data["HostConfig"]["ReadonlyRootfs"] is True
    assert data["HostConfig"]["CapDrop"] == ["ALL"]
    assert "no-new-privileges:true" in data["HostConfig"]["SecurityOpt"]
    uid = int(command([*compose, "exec", "-T", service, "id", "-u"]).strip())
    assert uid != 0
    evidence["containers"][service] = {
        "image_id": data["Image"],
        "uid": uid,
        "read_only": True,
        "memory_bytes": data["HostConfig"]["Memory"],
        "nano_cpus": data["HostConfig"]["NanoCpus"],
    }
    if service != "web":
        command(
            [
                *compose,
                "exec",
                "-T",
                service,
                "python",
                "-c",
                (
                    "import errno, pathlib, importlib.util; assert importlib.util.find_spec('pytest') is None; "
                    "p=pathlib.Path('/tmp/acceptance-write'); p.write_text('temporary'); p.unlink(); "
                    "\ntry: pathlib.Path('/app/acceptance-write').write_text('must fail')"
                    "\nexcept OSError as e: assert e.errno == errno.EROFS"
                    "\nelse: raise AssertionError('Application root is writable')"
                ),
            ]
        )
evidence["checks"].append({"non_root_read_only_tmp_runtime_dependencies": "passed"})
wait_status(200)
for service, wait_seconds in (
    ("minio", 60),
    ("redis", 40),
    ("heavy", 95),
    ("short", 95),
):
    started = time.monotonic()
    try:
        command([*compose, "stop", "-t", "2", service])
        down = wait_status(503, seconds=wait_seconds)
        evidence["checks"].append(
            {
                "stopped": service,
                "liveness": down["health"],
                "readiness": down["ready"],
                "status": down["status"],
                "detected_seconds": round(time.monotonic() - started, 2),
            }
        )
    finally:
        command([*compose, "start", service])
    restored = wait_status(200)
    evidence["checks"].append({"recovered": service, "readiness": restored["ready"]})
target = root / ".runtime/acceptance/safe-artifacts/runtime-infrastructure.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
print(json.dumps({"runtime_outage_checks": "passed", "evidence": str(target)}))
