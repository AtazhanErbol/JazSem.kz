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
