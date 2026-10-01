# Release evidence — 2026-10-01

The current [release report](../RELEASE_CANDIDATE.md) is authoritative. Final application/test source: `ac8ad868cdc6c2bf0067f7e731b5d5f581d2f96c`. The subsequent evidence commit changes documentation/JSON only; it does not represent another application build. No new remote CI or production acceptance is implied.

## Current evidence

- `test-summary.json`: all 145 PostgreSQL tests, eight concurrency cases, eight frontend tests and static/build/schema checks. Final backend JUnit is retained locally at `.runtime/final/backend-ac8.xml`.
- `browser-suite.json`: 21 actual Playwright tests, zero failed/skipped/flaky, source SHA and clean working-tree state at the test run. The real AI integration uses HTTP/outbox/Redis/Celery with only the SDK provider replaced. Separate mocked UI scenarios are named explicitly in the report.
- `postgres-before.json`, `postgres-after.json`, `postgres-before-100.json`, `postgres-after-100.json`: sequential same-host baseline `a712f64` versus final source, 25 and 100 enrollments, 25 visible result rows. Seven warm observations; nearest-rank p95 is the maximum of seven, not a production-tail estimate. Baseline application files were verified against Git; only the enrollment-count benchmark harness differs.
- `browser-before-comparable.json`, `browser-after.json`: fresh same-host production builds at baseline/final source, identical dataset, Chromium, network/CPU settings and measurement script. Seven cold navigations per route plus real language-toggle clicks. Event Timing is laboratory interaction evidence, not field INP. Route payload and total build bytes are separate. The original `browser-before.json` is historical and must not be paired with the current after file.
- `runtime-init.json`, `runtime-tls.json`, `runtime-http.json`, `runtime-infrastructure.json`, `runtime-faults.json`, `runtime-extras.json`, `proxy-clients.json`: fresh production-profile lab, real containers/queues/S3/STARTTLS and process/dependency faults. Proxy report source is recorded in `evidence-index.json` because the raw report is an array.
- `restore.json`: quiesced synthetic PostgreSQL/object/key restore into a separate database/bucket, all 43 model fingerprints including membership tables. Download validation uses a Django session HTTP client; real network HTTPS is separately tested.
- `dependency-scans.json`, `pip-*-audit.json`, `npm-audit.json`, `image-scans.json`, `secret-scans.json`: fresh scans. Condensed image data retain every finding and immutable image IDs. Full unsuppressed Trivy reports stay under ignored safe artifacts; the exact native-library review is `native-image-review.json` and [SECURITY_REVIEW](../SECURITY_REVIEW.md).
- `evidence-index.json`: SHA-256 of exported evidence, source/environment and gate status. It intentionally excludes itself and records the tested code SHA, not its own future commit SHA.

## Deliberate limits

Synthetic accounts use `example.test`; all databases/buckets are isolated. No paid provider call or real external email was made. A worker lease is deliberately expired after SIGKILL to test recovery without waiting ten minutes. S3 cleanup uses a 96-hour advanced command clock and stopped writers, not a real four-day wait. Actual 14.4-megapixel OCR tests bounded processing and short-queue isolation; a controlled timeout is an expected terminal failure, not a quality score. Accessibility coverage includes keyboard/focus and 200% text reflow, not a complete WCAG audit or true browser-zoom certification.

Raw traces, screenshots containing form data, reset URLs, mail bodies, database dumps, object payloads and secrets are never committed. Safe browser server metadata remains in `.runtime/browser-b22fd8f4/safe-artifacts/server-events.json`; raw failed-run evidence stays ignored. All local evidence is distinct from the old remote CI result at `a712f64`.

`backend-before.json` / `backend-after.json` are earlier SQLite lab observations. Historical logs and earlier partial results are in `docs/history/`; they are not current gates. Reproduction commands, limitations and remaining external conditions are in the release report and canonical deployment runbook.
