# JazSem.kz release candidate — final verification in progress

**Status: in progress, not approved for release.** Baseline: `release/rc-hardening` at `a712f644bcd7185bd9d99943ce499d0cb6943654`. All current changes are being verified locally; no push, PR, merge, tag, deployment or paid provider call is authorized by this task.

The historical [CI run 36696183172](https://github.com/AtazhanErbol/JazSem.kz/actions/runs/36696183172) verifies 125 PostgreSQL tests including eight concurrency cases, seven frontend unit tests and development infrastructure/builds at the baseline. It does not certify the new browser/runtime/fault/restore jobs. Earlier work logs and known-fixed A1–A4/deadlock findings are archived in [history](history/RELEASE_CANDIDATE_BEFORE_FINAL_VERIFICATION.md).

## Current 13-direction matrix

The final run will replace pending verification entries with exact counts and source SHA. Earlier local evidence is retained, not represented as a final clean-tree run.

| # | Direction | Implemented/evidence | Final status |
|---|---|---|---|
| 1 | Student owner/creator/history | Explicit owner, scope and PostgreSQL concurrency regressions | pending final suite |
| 2 | Access/validation/contracts | Nested scope, private files, answer-key protection, published immutability, strict 4xx, OpenAPI | pending final suite |
| 3 | Durable recovery | Real SIGKILL/broker/storage/SMTP; uncertain usage row and fail-closed Redis 503 fixed | pending rebuilt runtime |
| 4 | Administrator path | Browser creation/owner/group/course, operations/mail admin gates | pending final browser |
| 5 | Teacher authoring | Manual lifecycle, publish checklist, scoped actions, old enrollments unchanged | pending final browser |
| 6 | Student continuation | Validated URL/stored target, answer reload/server expiry, completion distinct from score | pending final browser |
| 7 | Filters/URL/pagination | Server allowlists, Back/Forward, filtered counts, RemoteSelect pages | pending final suite |
| 8 | Forms/feedback | Localized ARIA errors, discriminated results, duplicate-submit/dirty guards, modal focus | pending final browser |
| 9 | Performance | PG25/100 matched before/after, batched results, clone bulk copy, lazy routes, byte/query budgets | measured; final regression pending |
| 10 | AI workflow/cost | Real outbox/Redis/worker fake SDK; source retry/exclusion, review/regenerate/import, cancellation/uncertain costs | pending final suite |
| 11 | RU/KK/mobile/a11y | 390/768/1280, actual roles/forms/player/AI, keyboard drawer/modal and text zoom | pending final browser; language review external |
| 12 | Evidence-led cleanup | Removed unused retry setting/obsolete implementations; S3 manifest/references/grace | pending final S3 check |
| 13 | Release verification | CI startup/cleanup, production runtime, TLS/proxy, restore, scans, canonical runbooks | in progress |

Canonical upgrade/rollback: [DEPLOYMENT](DEPLOYMENT.md). Native image findings and exact review scope: [SECURITY_REVIEW](SECURITY_REVIEW.md). Measurements: [directory](measurements/).

## External gates (not local failures)

Target DNS/TLS/proxy chain, managed PostgreSQL/Redis/S3 versions and IAM; actual SMTP TLS/inbox; separately approved paid AI sample with model/price/limit and RU/KK/citation quality; real OCR and subject/language editing; actual contacts/legal content; configured alerts and encrypted backup retention/access/restore. Owner approval of residual native-library risk remains required. A new GitHub Actions result requires separately authorized push/PR. No target production or staging success is inferred from this lab.
