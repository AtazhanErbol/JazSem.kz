"""Start isolated services, require a fresh synthetic DB, run every E2E and clean up.

Set DATABASE_URL (jazsem_rc_* on loopback), E2E_REDIS_URL, DEV_SEED_PASSWORD.
Private raw logs/traces stay under ignored .runtime/test-results. Only sanitized
summaries and action timings are exported to the safe artifacts directory.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
runtime = root / ".runtime" / ("browser-" + uuid.uuid4().hex[:8])
runtime.mkdir(parents=True)
safe = runtime / "safe-artifacts"
safe.mkdir()
env = os.environ.copy()
for required in ("DATABASE_URL", "E2E_REDIS_URL", "DEV_SEED_PASSWORD"):
    if not env.get(required):
        raise SystemExit(required + " is required; mandatory E2E cannot be skipped")
backend_port = int(env.get("E2E_BACKEND_PORT", "8008"))
frontend_port = int(env.get("E2E_FRONTEND_PORT", "5182"))
smtp_port = int(env.get("E2E_SMTP_PORT", "1025"))
mail_port = int(env.get("E2E_MAIL_PORT", "8025"))
env.update(
    {
        "DJANGO_SETTINGS_MODULE": "config.settings.e2e",
        "E2E_ISOLATED": "1",
        "JAZSEM_RUNTIME_DIR": str(runtime),
        "FRONTEND_URL": f"http://127.0.0.1:{frontend_port}",
        "CSRF_TRUSTED_ORIGINS": f"http://127.0.0.1:{frontend_port}",
        "API_PROXY": f"http://127.0.0.1:{backend_port}",
        "E2E_BASE_URL": f"http://127.0.0.1:{frontend_port}",
        "E2E_MAIL_URL": f"http://127.0.0.1:{mail_port}",
        "E2E_SMTP_PORT": str(smtp_port),
        "CI": "true",
        "E2E_FAKE_PROVIDER": "1",
        "AI_ENABLED": "false",
        "OPENAI_API_KEY": "",
        "SENTRY_DSN": "",
    }
)
processes = []
streams = []


def run(args, cwd=root / "backend", log="setup"):
    with (runtime / (log + ".log")).open("ab") as stream:
        subprocess.run(args, cwd=cwd, env=env, stdout=stream, stderr=stream, check=True)


def start(name, args, cwd):
    stream = (runtime / (name + ".log")).open("wb")
    streams.append(stream)
    process = subprocess.Popen(
        args,
        cwd=cwd,
        env=env,
        stdout=stream,
        stderr=stream,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    processes.append(process)


def ready(url):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("An acceptance service exited before readiness")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    raise RuntimeError("Acceptance service readiness timeout")


def evidence():
    report = json.loads((runtime / "playwright.json").read_text(encoding="utf-8-sig"))
    tests = []

    def collect(suite):
        for spec in suite.get("specs", []):
            for test in spec["tests"]:
                tests.append(
                    {
                        "file": spec["file"],
                        "line": spec["line"],
                        "title": spec["title"],
                        "status": test["status"],
                        "runs": [
                            {
                                "status": result["status"],
                                "duration_ms": result["duration"],
                            }
                            for result in test.get("results", [])
                        ],
                    }
                )
        for child in suite.get("suites", []):
            collect(child)

    collect(report)
    summary = {
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "dirty_tree": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=root, text=True
            ).strip()
        ),
        "stats": report["stats"],
        "tests": tests,
    }
    (safe / "browser-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    # Allowlist structured server metadata. Never export raw Django runserver
    # access lines: they include reset links and searchable user input in URLs.
    safe_logs = []
    for service in ("backend", "worker", "beat"):
        for line in (
            (runtime / (service + ".log"))
            .read_text(encoding="utf-8", errors="replace")
            .splitlines()
        ):
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            safe_logs.append(
                {
                    "service": service,
                    **{
                        key: event[key]
                        for key in (
                            "asctime",
                            "levelname",
                            "name",
                            "request_id",
                            "duration_ms",
                            "status_code",
                            "error_type",
                            "task_id",
                            "job_id",
                            "source_id",
                            "error_code",
                        )
                        if key in event
                    },
                }
            )
    (safe / "server-events.json").write_text(json.dumps(safe_logs), encoding="utf-8")
    # Export timings/action names only. Raw trace snapshots, request/response
    # bodies, URLs, fill values and screenshots can contain reset credentials.
    for index, trace in enumerate((root / "frontend/test-results").glob("*/trace.zip")):
        timeline = []
        with zipfile.ZipFile(trace) as archive:
            for name in archive.namelist():
                if not name.endswith(".trace"):
                    continue
                for line in archive.read(name).splitlines():
                    row = json.loads(line)
                    if row.get("type") in {"before", "after", "console", "event"}:
                        timeline.append(
                            {
                                key: row[key]
                                for key in (
                                    "type",
                                    "callId",
                                    "class",
                                    "method",
                                    "apiName",
                                    "startTime",
                                    "endTime",
                                )
                                if key in row
                            }
                        )
        (safe / f"failed-trace-{index}-timings.json").write_text(
            json.dumps(timeline), encoding="utf-8"
        )
    print(json.dumps({"stats": report["stats"], "safe_artifacts": str(safe)}))
    if not tests or any(row["status"] in {"skipped", "unexpected"} for row in tests):
        raise RuntimeError("Mandatory browser scenarios failed or were skipped")


try:
    run([sys.executable, "manage.py", "migrate", "--noinput"])
    run(
        [
            sys.executable,
            "manage.py",
            "shell",
            "-c",
            "from apps.accounts.models import User; assert User.objects.count() == 0, 'Fresh synthetic DB required'",
        ]
    )
    run([sys.executable, "manage.py", "seed_dev"])
    start(
        "smtp",
        [
            sys.executable,
            str(root / "scripts/acceptance_mail.py"),
            "--smtp-port",
            str(smtp_port),
            "--http-port",
            str(mail_port),
        ],
        root,
    )
    start(
        "backend",
        [
            sys.executable,
            "manage.py",
            "runserver",
            f"127.0.0.1:{backend_port}",
            "--noreload",
        ],
        root / "backend",
    )
    start(
        "worker",
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "config",
            "worker",
            "--pool=solo",
            "--concurrency=1",
            "--loglevel=warning",
        ],
        root / "backend",
    )
    start(
        "beat",
        [sys.executable, "-m", "celery", "-A", "config", "beat", "--loglevel=warning"],
        root / "backend",
    )
    start(
        "frontend",
        [
            shutil.which("node"),
            "node_modules/vite/bin/vite.js",
            "--host",
            "127.0.0.1",
            "--port",
            str(frontend_port),
            "--strictPort",
        ],
        root / "frontend",
    )
    ready(f"http://127.0.0.1:{mail_port}/health")
    ready(f"http://127.0.0.1:{backend_port}/ready/")
    ready(env["E2E_BASE_URL"])
    print(
        "Isolated PostgreSQL/Redis/SMTP/browser services ready; running full E2E.",
        flush=True,
    )
    with (
        (runtime / "playwright.json").open("wb") as output,
        (runtime / "browser-errors.log").open("wb") as errors,
    ):
        result = subprocess.run(
            [
                shutil.which("node"),
                "node_modules/@playwright/test/cli.js",
                "test",
                "--reporter=json",
            ],
            cwd=root / "frontend",
            env=env,
            stdout=output,
            stderr=errors,
            check=False,
        )
    evidence()
    if result.returncode:
        raise SystemExit(result.returncode)
    run(
        [shutil.which("node"), "node_modules/vite/bin/vite.js", "build"],
        cwd=root / "frontend",
        log="production-build",
    )
    preview_port = frontend_port + 1
    start(
        "production-preview",
        [
            shutil.which("node"),
            "node_modules/vite/bin/vite.js",
            "preview",
            "--host",
            "127.0.0.1",
            "--port",
            str(preview_port),
            "--strictPort",
        ],
        root / "frontend",
    )
    ready(f"http://127.0.0.1:{preview_port}")
    env["MEASURE_URL"] = f"http://127.0.0.1:{preview_port}"
    env["MEASURE_OUT"] = str(safe / "browser-performance.json")
    run(
        [shutil.which("node"), "e2e/measure.mjs"],
        cwd=root / "frontend",
        log="performance",
    )
    print(
        "Production route/build byte budgets passed; interaction timings saved.",
        flush=True,
    )
finally:
    for process in reversed(processes):
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
    for stream in streams:
        stream.close()
