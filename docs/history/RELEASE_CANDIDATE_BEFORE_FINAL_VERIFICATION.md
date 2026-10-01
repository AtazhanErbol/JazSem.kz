> Historical checkpoint, superseded by ../RELEASE_CANDIDATE.md.

# Release candidate work log — 2026-09-30

Status: **in progress, not approved for release**. Source branch `feat/admin-workspace-guide`, SHA `a8e76869a4cafc268853973c8b0bd3f4d1083609`. Work branch `release/rc-hardening`. Source tree was clean; no user changes to preserve. Original application DB and external services are not acceptance fixtures.

## Plan and acceptance gates

Scope updated by the owner's replacement prompt on 2026-09-30: all 13 directions are mandatory (ownership, access/validation, recovery, admin path, teacher workspace, student continuation, real filters, form feedback, performance, AI recovery/history/costs, mobile RU/KK, evidence-based cleanup, release verification). A core-only checkpoint is intermediate; AI work with a fake provider cannot be omitted. The previous baseline and compatible changes are retained.

1. A — reproduce and fix ownership, question exposure, account activity and custom-action validation; additive/data migrations and access regression tests.
2. B — transactional task delivery and leases, source recovery/snapshots, encrypted mail recovery, bounded extraction/file lifecycle, grading-mode consistency.
3. C — data/locking invariants, production configuration/proxy/health, redacted observability/audit, isolated restore rehearsal.
4. D/E — typed mutation outcomes and field errors, URL state and accessible flows; measure then optimize query/bundle costs; evidence-based cleanup.
5. F — PostgreSQL concurrency, real-service fault injection, mandatory browser lifecycle in CI, production-image smoke/scans/artifacts; update operator runbooks and list open infrastructure gates.

Each stage is checked before the next commit. Paid AI, real SMTP and site deployment are excluded. Synthetic accounts use `example.test`; local mail sink and test provider only. Production acceptance requires real staging evidence, not unit-test totals.

## Baseline observed locally

- Windows / Python 3.12.14 / Node 24.21.0; CI pins Python 3.12 and Node 22.
- `config.settings.test`, isolated in-memory SQLite, eager test Celery and locmem email. This does **not** verify PostgreSQL locks or broker delivery.
- Ruff lint/format, Django check, migration drift and pip consistency: pass.
- Backend: 51 passed; frontend: 5 passed. ESLint, TypeScript and production build pass.
- OpenAPI: 0 errors, 2 enum naming warnings. Baseline saved to ignored `.runtime/rc/baseline-openapi.yml`.
- Build JS: 604.57 kB raw / 184.93 kB gzip; CSS: 52.63 / 12.05 kB. These are build sizes, not LCP measurements.
- Docker, PostgreSQL CLI and GitHub CLI unavailable in local PATH. Real PostgreSQL/container tests will run in isolated GitHub Actions jobs; external staging/restore remain open until evidenced.
- Historical audit/dependency scan results are not treated as fresh proof.

## Findings register

| ID | Priority / evidence | Reproduction and impact | Location | Fix / regression / status |
|---|---|---|---|---|
| A1 | P1 confirmed | Admin creates STUDENT; group membership returns 400 because creator is interpreted as owner | accounts, scope, enrollments | `test_admin_created_student_can_join_owner_group_and_course` fails on baseline; fix pending |
| A2 | P1 confirmed | Future test cannot start but student authoring question/option lists return 200 | common API, testing | two `test_student_cannot_read_authoring_questions_before_start` cases fail; fix pending |
| A3 | P1 confirmed | Admin PATCH self `is_active=false` returns 200 | accounts views | `test_patch_cannot_bypass_self_deactivation_policy` fails; fix pending |
| A4 | P1 confirmed | Submission null/object/list/number/bool causes 500 | assignments actions | five field-error regression cases fail; fix pending |
| B1–B5 | hypotheses from supplied review | Delivery/recovery, stale workers, sources, SMTP, resource limits, ungraded-course dead end | AI, notifications, materials | inspect, reproduce, fix and record evidence |
| C | hypotheses from supplied review | Lock order, proxy identity, production startup and restore | testing, infra, config | PostgreSQL and production-profile gates pending |
| D/E | hypotheses from supplied review | Failure UX, overfetching, bundle cost, dead code | frontend, read models | measure and verify before changes |

Initial regression run: **9 failed**, reproducing A1–A4; normal baseline tests remain green. No production data was changed. These nine cases now pass; broader contracts remain in progress. A browser run additionally exposed a logout/login race: global invalidation redirected the next session after a delayed protected refetch. Auth session transitions now avoid those refetches; browser verification is pending.

## Stage A implementation checkpoint

Added `accounts.0003_student_owner_teacher`: nullable PROTECT owner, role constraint and data copy only from teacher creators. Administrative/unknown creators remain unassigned. Creator and historical rows are preserved. Generic reassignment rejects conflicting course/group history; only ADMIN can change ownership.

Question/option authoring endpoints now require an author role. Students review only their permitted attempts, without answer keys. Account activity updates share a stable administrator lock set and prohibit self-blocking; PostgreSQL race regression is included.

Runtime input serializers validate coursework, grading, revisions, version/course/group assignment and answers. Forms choose ownership and retain field errors; edit forms expose a fixed role. Mutation outcomes distinguish empty success from failure and prevent duplicate in-flight actions. Confirmation and upload state survive failed requests.

Local checkpoint: **68 backend passed, 2 PostgreSQL-only skipped**; **7 frontend passed**, lint/typecheck/build pass. Migration tested from historical accounts schema and on a new synthetic QA DB. PostgreSQL concurrency and expanded contracts/observability remain gates, not assumed successes.

QA app: ports 8006/5179, isolated `.runtime/rc/qa.sqlite3`, AI disabled, filebased email, no production records. Rollback: do not revert the ownership schema after newly owned admin-created students exist; roll back to a compatible application image or migrate ownership explicitly. The data-copy reverse is intentionally a no-op and never rewrites creator history.

Stage A commit `5cf22c3` pushed to `release/rc-hardening`. [CI run 36689475086](https://github.com/AtazhanErbol/JazSem.kz/actions/runs/36689475086) passed backend (real PostgreSQL, including both concurrency tests), frontend and containers. Existing 15 browser scenarios passed on a fresh `.runtime/rc2/qa.sqlite3` (8006/5179). A sixteenth session-transition scenario hit the real auth throttle in the full run and passed separately after quota reset; this is recorded rather than presenting the full run as green. CI browser isolation/rate policy remains to be completed.

## Mail recovery checkpoint

B3 reproduced with three failing regressions (SMTP lock duration, silent failure/backoff, missing operator retry). Implemented explicit delivery states, short claims, expiring leases, fenced completion, bounded delayed retries, admin-only metadata/retry/metrics, key rotation and a RU/KK operator screen. `notifications.0002_delivery_leases` preserves old queued records and marks exhausted deliveries for review. See MAIL_RECOVERY.md.

Local check before AI changes: **73 backend passed, 2 PostgreSQL-only skipped**, **7 frontend passed**, lint/typecheck pass. Lease/rotation tests include missing keys and retained ciphertext. No real recipient or paid provider was contacted. Production SMTP and competing PostgreSQL mail claims are still acceptance gates.

## AI recovery checkpoint

B1/B2 reproduced with three failing API regressions: broker loss after commit returns 500, a failed source blocks a valid selection, and exclusion is missing. Added transactional delivery outbox, stable identity, bounded dispatch/execution retries, expiring leases and fenced completion; persistent source snapshots; course lock and active-job uniqueness; explicit AI input/read contracts; early assessed-activity validation. Sources support retry/exclusion, UI selection and paginated history/costs; polling stops on terminal/error state. No real provider calls.

Local checkpoint: **87 backend passed, 5 PostgreSQL-only skipped**, migration drift/lint/format/typecheck pass; mocked AI browser review/import passes. New tests simulate hard death after budget reservation, cancellation during provider response, duplicate delivery and late completion. PDF/OOXML/image limits have fixtures; renderer resource closure is exercised. Real process/broker/SMTP fault injection, orphan storage cleanup and container resource separation are still pending. Migration/operating semantics: BACKGROUND_RECOVERY.md.

## Locking reproduction

C3 is confirmed on PostgreSQL: [run 36691868557](https://github.com/AtazhanErbol/JazSem.kz/actions/runs/36691868557), commit `0394043`, failed only `test_start_and_expire_follow_one_lock_order` with `deadlock detected` (92 passed). Separate connections/events forced start's Enrollment lock against finalization's Attempt lock. This also verifies the five preceding PostgreSQL cases (admin deactivation, enrollment, cross-actor AI uniqueness, mail claim, budget cap). Finalization now takes Enrollment → Attempt, matching start, and reuses the locked enrollment for progress persistence; fixed-run evidence is pending.

Fixed run [36692180974](https://github.com/AtazhanErbol/JazSem.kz/actions/runs/36692180974), SHA `d956ec5`, passed all three jobs including the PostgreSQL deadlock regression.

C5 reproduced with two failed tests: forged XFF bypassed the login quota, and different clients behind a proxy shared a quota. Added explicit trusted-peer normalization, spoofed-header removal and REMOTE_ADDR-based throttling; both regressions pass. Added fail-fast production validation, domain-aware liveness, redacted stack frames and request/error correlation. Production-image/proxy-chain smoke remains required. B4 filename replacement regression failed before the metadata fix; dry-run orphan cleanup now rechecks shared references and grace age before deletion. Only synthetic filesystem fixtures were removed.

CI [36692985280](https://github.com/AtazhanErbol/JazSem.kz/actions/runs/36692985280) passed at `87ef76e`. Continued A4 with explicit sensitive resource fields, strict auth/profile/action inputs, mode-specific auth form payloads and nested OpenAPI outputs for student/author trees, attempts, grading, AI, files and recovery. A new malformed-body regression found the strict-input base itself incorrectly raising a non-field string, resulting in 500; it now returns structured 400. Six contract regressions pass; OpenAPI validation now finishes with **zero errors and zero warnings**, including enum names. Schema drift gate will be added with the release pipeline.

## States, operations and measurement checkpoint

Added state CHECK constraints for course/version/enrollment/submission/attempt/job/source, a counts-only preflight, course/version lock ordering, group/course/student inheritance ordering and new PostgreSQL group/publication races. Added explicit audit metadata, worker/queue/storage metrics, private admin operations endpoint and separate resource-capped heavy queue. Local: **117 passed, 8 PostgreSQL-only skipped**, lint/format/migration drift and OpenAPI validation pass. Read-only production containers and real worker/proxy faults still require the expanded CI gate.

Performance baseline is recorded in `docs/measurements/*-before.json`. Backend: isolated SQLite synthetic course at `4bada2d`, 33 topics, 257 questions, 1,026 options, 25 enrollments, seven samples; this is a query/lab baseline, not PostgreSQL load capacity. Corrected the measurement harness after Django's 9,000-query deque truncated late duplicate samples, then reran the **same pre-optimization source** from `git archive 4bada2d` with only query-log clearing changed. All seven duplicate samples now record 1,799 queries. Browser: production build, seven cold contexts per landing/login route, 1440×900, 4× CPU slowdown, 40 ms / 5 Mbit down, Chromium version and actual request paths captured; INP is not measured by these passive navigations. No speedup claimed yet.

CI at `4bada2d` ([36694972475](https://github.com/AtazhanErbol/JazSem.kz/actions/runs/36694972475)) passed backend/containers but failed frontend lint because the new measurement script lacked explicit browser/Node global declarations. This harness lint error is fixed; no passing full CI claim for that SHA.


## 2026-10-01: continued acceptance on the working tree

The renewed owner request references `a712f644bcd7185bd9d99943ce499d0cb6943654`; it remains HEAD. Preserve the existing RC branch and uncommitted work. No merge/tag/deployment is authorized. The new request requires separate explicit authorization for push/PR; prepare a reviewable result before that step.

CI [36696183172](https://github.com/AtazhanErbol/JazSem.kz/actions/runs/36696183172) passed on a712f64, including all eight PostgreSQL concurrency tests. Those are verified, not open hypotheses. Production runtime, restore and full process-fault gates were absent from that run.

Current local implementation adds lazy routes and role-specific builder/player, continuation, paginated remote selectors, scoped query updates, real URL filters/order, a batched enrollment summary, teacher work queues, answer retry persistence, form protection/accessibility, domain details and improved review forms. Historical JSON input/ownership/access regressions remain intact. SQLite focused workspace/summary checks passed; the complete backend suite then passed **130 tests on PostgreSQL 16.15** (Python 3.12.14 on Windows, dedicated Docker/WSL database). Initial PostgreSQL test invocation failed at pytest's Windows temporary-directory permissions, before fixtures ran; a fresh workspace-owned basetemp resolved this. Do not mistake those setup errors for product regressions.

A new real browser lifecycle passed in **54.3 seconds** on PostgreSQL + Redis 7.4.11 + a separate Celery process + the local SMTP sink: ADMIN creates/edits teacher, discipline, owned student and group; first-account email and required password change; password reset; manual course/material/file/assignment/test/grading/publication/group assignment; student file upload, revision/resubmission, test refresh and grading; published v2 preserves the student's v1 enrollment, score 90 and progress 100. Synthetic `example.test` addresses only; no external mail or paid AI. This is a focused pass, not yet the final whole-suite result or production TLS/profile proof.

Earlier full browser run on SQLite: 12 passed / 4 failed. Failures were stale expected labels/mocked endpoint/detail content and a missing wait for selected options. They have been updated; the final PostgreSQL full run is still pending. A concurrent SMTP/HTTP local SQLite run hit OperationalError; acceptance moved to PostgreSQL rather than changing production locking policy.

Docker Engine 29.1.3 / Compose 2.40.3 were installed in the existing Ubuntu 26.04 WSL for isolated runtime verification. WSL needs a live task process during checks; otherwise its idle shutdown stops Docker containers. QA service ports are 8008/5182; PostgreSQL 15432 and Redis 16379 bind loopback. Runtime manifests and private synthetic mail are ignored under `.runtime`; do not upload raw mail/credentials/traces.

Cleanup evidence so far: no current TSX/dynamic-class references to the removed main.css `.visual-label`, `.orbit`, `.orbit-two`, `.book`, `.book-front`, `.book-back`, `.book-face`, `.book-spine` block; current BookScene uses its own classes. Removed unreachable student branches from the teacher builder and the unreachable admin KPI branch from LearningDashboard. No fonts were removed. Runtime/dev requirements now resolve separately with unchanged runtime versions; xlsxwriter remains required by python-pptx. Final build/image/dependency gates are still pending.

Do not report the preliminary `backend-after.json` timing as final: it was taken alongside other work. Repeat baseline/current sequentially on PostgreSQL with identical data, then record raw observations and clear limitations. Bulk option inserts are now covered by clone equality/independence/rollback checks; final metrics and final-SHA validation remain pending.


## 2026-10-01: browser lifecycle and production runtime evidence (working tree)

Still **in progress; not approved for release**. HEAD remains a712f644bcd7185bd9d99943ce499d0cb6943654; these results include uncommitted engineering changes and are not a new GitHub CI result. No push/PR/deployment performed.

- Full automated startup/migrate/fresh seed/readiness/Playwright/cleanup passed **18 tests, 0 failed, 0 skipped, 0 flaky**, 210.85 seconds, using isolated PostgreSQL 16.15, Redis 7.4.11, loopback SMTP sink and Chromium. Evidence: `docs/measurements/browser-suite.json`; safe raw summary: `.runtime/browser-d9e4fed5/safe-artifacts/`. The preceding 17/18 run exposed a real repeated-Escape native dialog defect; intercepting keydown before the native close action fixed it. Focused regression passed, then the entire suite passed on fresh DB `jazsem_rc_e2e_run4`. Earlier setup failures from a wrong base URL and reused Redis throttle state were not product passes; acceptance caches now have a per-database prefix, with production limits unchanged.
- Forms regression verifies localized required/field errors, accessible field associations and focus, preserved values after 400/403/409/429/503, duplicate-submit prevention, pending Escape, discard/reopen and focus restoration. Assignment route IDs now reset component state; unavailable browser storage does not crash assignment/player pages.
- New schema-compatible `release_preflight --legacy` defers only the known absent ownership/mail-state columns. Normal preflight fails closed until these migrations exist. Actual historical-schema migration test and counts-only ownership-conflict test passed. Focused security/state/config suite: 19 passed. Final full PostgreSQL suite remains pending after these changes.
- Production images actually ran non-root/read-only, writable `/tmp`, production settings, PostgreSQL, private MinIO, TLS Redis, STARTTLS SMTP sink, short/heavy workers, beat and HTTPS edge. Production runtime excludes pytest/dev dependencies. Real Celery broker/result clients accepted the trusted CA and rejected an untrusted CA; hostname mismatch also rejected. HTTPS/static routes, Host validation, secure cookies, missing-CSRF rejection, administrator operations/mail access, anonymous S3 rejection and queued STARTTLS delivery passed. This is a synthetic local lab, not target-infrastructure approval.
- Real process outages passed: stop S3 -> readiness 503 after 21.63s; Redis -> 503 after 2.23s; heavy/short worker freshness -> 503 after 62.52s / 64.34s. Liveness remained 200; every dependency restart returned readiness to 200. Evidence: `docs/measurements/runtime-infrastructure.json`. Local proxy peer is explicitly .30 instead of production host gateway .1; all other web proxy logic comes from the production config. These checks do not yet cover provider-boundary worker kill, SMTP claim faults or restore.
- Redis TLS policy now sets CERT_REQUIRED and hostname checking consistently for cache/broker/result/readiness; URL ssl_* overrides are rejected. Access logs exclude query strings. Sentry error filtering removes request bodies/cookies/query tokens, breadcrumbs, arbitrary context and exception values/locals; regression passed.
- PostgreSQL before/after measured sequentially against archived a712f64 and current code, same 33-topic/257-question/1026-option/25-enrollment dataset, seven warmed observations. Raw JSON: `postgres-before.json`, `postgres-after.json`. Query counts: student tree 12 -> 10, same 121233 bytes; editor 11 -> 11, same 431899 bytes; publish 59 -> 27; duplicate 1803 -> 391. Legacy combined progress+grades remains 50 HTTP calls and worsened 375 -> 400 queries (median 805.15 -> 1097.82ms); it is no longer the UI path. New visible-page summaries: 1 HTTP, 11 queries, 20689 bytes, median 49.13ms. This adds names/progress/grades to the response; do not compare byte totals as identical contracts. Duplicate median 1489.68 -> 465.99ms. Seven-sample maxima labelled p95 are descriptive lab observations, not production tail/capacity estimates. Larger dataset/browser-after/budgets still pending. Host: i5-11400H, 6 cores/12 logical processors, Windows 11 with PG in WSL Docker.
- Fresh pip-audit: 70 runtime packages and 104 dev packages, zero known findings. npm audit: zero known findings. Raw reports remain under `.runtime/acceptance/`. Container scan is running; secret scan remains pending. Runtime/dev lockfiles are separated without an intentional runtime dependency upgrade.
- Added CI jobs for mandatory full browser lifecycle and actual production runtime/outages, plus schema drift validation. They have been exercised locally through their harnesses, but have **not run on GitHub** for this working tree. Raw browser traces may contain synthetic credentials, so CI uploads only sanitized summaries/action timings, not raw snapshots/bodies/screenshots.

Remaining engineering work: real-worker fake-provider AI integration and failure cases; SMTP delivery/lease and storage extraction faults; restore rehearsal with matching objects/keys; current image/secret scan triage; production proxy spoof/throttle multi-client checks; broader mobile/keyboard/file-error acceptance; final PostgreSQL/schema/performance/browser gates; consistent upgrade/rollback runbooks and final 13-direction matrix. These are not external blockers. Actual DNS/TLS/inbox/paid-AI quality/real-document OCR/legal content/operational ownership remain separate external gates.
