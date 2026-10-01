"""Fresh image scans; exact reviewed native findings never mean a clean scan."""

import collections
import datetime
import json
import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = root / ".runtime/acceptance/safe-artifacts"
output.mkdir(parents=True, exist_ok=True)
review = json.loads((root / "docs/measurements/native-image-review.json").read_text())
scanner = "aquasec/trivy@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969"
images = {
    "backend": "jazsem-backend:acceptance",
    "frontend": "jazsem-frontend:acceptance",
    "postgres": "postgres:16-alpine",
    "redis": "redis:7-alpine",
    "minio": "jazsem-acceptance-minio",
}
report = {
    "source_ref": os.environ.get("RC_SOURCE_REF", "working tree"),
    "scanner": scanner,
    "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "images": {},
}
blocking = []
for name, reference in images.items():
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            "/var/run/docker.sock:/var/run/docker.sock",
            "-v",
            "jazsem-acceptance-trivy-cache:/root/.cache/",
            "-v",
            str(output) + ":/reports",
            scanner,
            "image",
            "--quiet",
            "--scanners",
            "vuln",
            "--format",
            "json",
            "--output",
            f"/reports/trivy-{name}.json",
            reference,
        ],
        check=True,
    )
    raw = json.loads((output / f"trivy-{name}.json").read_text())
    findings = [
        {
            "id": v["VulnerabilityID"],
            "package": v["PkgName"],
            "installed": v["InstalledVersion"],
            "fixed": v.get("FixedVersion", ""),
            "severity": v["Severity"],
        }
        for result in raw.get("Results", [])
        for v in result.get("Vulnerabilities", [])
    ]
    report["images"][name] = {
        "image_id": raw["Metadata"]["ImageID"],
        "repository_digests": raw["Metadata"].get("RepoDigests", []),
        "counts": dict(collections.Counter(v["severity"] for v in findings)),
        "findings": findings,
        "scope": "production application"
        if name in {"backend", "frontend"}
        else "isolated synthetic lab only; managed services required for deployment",
    }
    if name in {"backend", "frontend"}:
        for item in findings:
            if item["severity"] not in {"HIGH", "CRITICAL"}:
                continue
            reviewed = any(item == entry["finding"] for entry in review["findings"])
            if (
                item["fixed"]
                or not reviewed
                or datetime.datetime.now(datetime.timezone.utc).date()
                > datetime.date.fromisoformat(review["review_by"])
            ):
                blocking.append({"image": name, **item})
report["unreviewed_or_fixable_production_high_critical"] = blocking
(output / "image-scans.json").write_text(json.dumps(report, indent=2))
print(
    json.dumps(
        {
            "images": {
                name: value["counts"] for name, value in report["images"].items()
            },
            "blocking": len(blocking),
        }
    )
)
if blocking:
    raise SystemExit(
        "Review new/fixable production findings; full unsuppressed reports retained"
    )
