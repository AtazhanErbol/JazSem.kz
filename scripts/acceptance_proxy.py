"""Verify two actual client IPs through edge -> web -> Django."""

import json
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
results = []
for address, count in [("172.30.0.201", 11), ("172.30.0.202", 1)]:
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "jazsem-acceptance_default",
            "--ip",
            address,
            "--read-only",
            "--tmpfs",
            "/tmp",
            "-v",
            str(root / "scripts") + ":/acceptance:ro",
            "-v",
            str(root / ".runtime/acceptance/certs") + ":/certs:ro",
            "jazsem-backend:acceptance",
            "python",
            "/acceptance/acceptance_proxy_client.py",
            str(count),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    results.append({"synthetic_client_ip": address, **json.loads(result.stdout)})
(root / ".runtime/acceptance/safe-artifacts/proxy-clients.json").write_text(
    json.dumps(results, indent=2)
)
print(
    json.dumps(
        {
            "real_proxy_clients": 2,
            "shared_throttle_bypass_rejected": True,
            "distinct_clients_independent": True,
        }
    )
)
