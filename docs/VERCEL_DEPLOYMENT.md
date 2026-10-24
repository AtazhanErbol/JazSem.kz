# JazSem on Vercel

## Current state

The `vercel-deploy` branch contains the initial deployment configuration.
`codex/vercel-deploy` contains the candidate full Vercel adaptation in
draft PR #1. The main branch is unchanged.

- React and Django build successfully on Vercel after declaring the locked Python
  runtime dependencies in `backend/pyproject.toml`.
- The landing page and login form render in the preview.
- The candidate has connected PostgreSQL, Redis, private storage, SMTP and both
  queue roles. Cloud `/ready/` returned `{"status":"ready"}` after real queue
  probes, embedded OCR initialization and the maintenance scheduler completed.
- A real password-reset email reached the owner. The initial owner's password
  still needs to be set personally through the email flow.
- `jazsem.vercel.app` has no production deployment yet. Preview access is protected
  by Vercel Authentication. Public production promotion still needs authorization.

## Runtime and security

`tool.vercel.entrypoint` uses `config.vercel_wsgi:application`. This entrypoint
requires `VERCEL=1`, production settings, and the fixed in-process trusted peer
`127.0.0.1/32`. It adapts Vercel's documented, edge-overwritten X-Forwarded-For
header into the existing trusted-proxy contract. It rejects missing, ambiguous,
or invalid edge headers before Django and ignores caller-supplied private-proxy
headers. The standalone Docker deployment still uses `config.wsgi`.

The backend service explicitly declares `entrypoint: "pyproject.toml"` so the
Python builder includes both the declared web entrypoint and private Celery
subscriber. Without this, Django framework discovery can omit the subscriber.
The build wrapper configures strict production settings before static collection;
Preview uses Vercel's validated exact `VERCEL_BRANCH_URL` for its origin and host.

Production validation, HTTPS redirects, secure cookies, CSRF and explicit allowed
hosts remain enabled. Do not set development settings to make the preview appear
functional. Keep AI disabled until separately configured and authorized.

## Required services and variables

Provisioned on confirmed free tiers: Neon `jazsem-postgres` (Production and
Preview, isolated database branches for Preview), Upstash `jazsem-redis`
(Production and Preview), and the private Tigris bucket
`jazsem-private-atazhan1`. All are connected only to `jazsem`. Provider-managed
credentials are injected into Vercel; their values are not stored in this repo.
The Vercel entrypoint maps `TIGRIS_STORAGE_*` to the existing S3 settings, using
the global HTTPS endpoint and `auto` region. Explicit S3 settings take precedence.

Common Vercel configuration was saved for Production and Preview:
`DJANGO_SETTINGS_MODULE=config.settings.production`,
`TRUSTED_PROXY_CIDRS=127.0.0.1/32`, `AI_ENABLED=false`, and exact allowed hosts
for `jazsem.vercel.app` and the stable `vercel-deploy` preview alias.
Separate application signing and mail encryption keys were generated and saved
as write-only secrets for Production and Preview. Environment-specific frontend
and CSRF origins were saved: the production domain for Production and the stable
deployment-branch alias for Preview. Gmail SMTP is configured for both environments;
the password was saved personally by the owner. Candidate migrations and the
empty-database owner bootstrap have run successfully.

Create a new isolated deployment database; do not connect previews to a live
customer database. The requested budget is zero: select only confirmed free
plans and do not enable paid upgrades or overage billing.

- PostgreSQL: set a real `DATABASE_URL` using TLS, preferably the provider's
  pooled endpoint for Functions.
- Redis: set authenticated `rediss://` in `REDIS_URL`. The application uses native
  Redis, including Celery; an HTTP-only Redis API is not a substitute.
- Private S3-compatible storage: `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`,
  `S3_SECRET_KEY`, `S3_REGION`. Verify bucket privacy and signed downloads.
- SMTP: `EMAIL_HOST`, `EMAIL_PORT`, the appropriate credentials,
  `EMAIL_USE_TLS` / `EMAIL_USE_SSL`, and a real `DEFAULT_FROM_EMAIL`.
- Generate and securely store `DJANGO_SECRET_KEY` and `MAIL_ENCRYPTION_KEY`.
  Never commit their values or put them in build logs.
- Set `DJANGO_SETTINGS_MODULE=config.settings.production`,
  `TRUSTED_PROXY_CIDRS=127.0.0.1/32`, exact `DJANGO_ALLOWED_HOSTS`, HTTPS
  `FRONTEND_URL`, and exact `CSRF_TRUSTED_ORIGINS` for the deployment being tested.
  Do not use wildcard hosts or origins.

## Full application release work

After connecting the isolated database, inspect its migration state and apply
forward migrations, run `release_preflight` and `check --deploy`, create a real
administrator, and initialize the private sentinel using `storage_probe
--initialize`. For an empty deployment, set `INITIAL_ADMIN_EMAIL` to the owner
email: the build creates username `owner` with an unusable password. Activate it
through the existing password-reset email flow. Existing administrators are left
unchanged; a nonempty database without one requires manual administration.
Production must not use `seed_dev`.

The standalone Docker deployment retains its original Celery workers and beat
scheduler. Vercel instead uses private queue-triggered Celery subscribers for both
explicitly declared queues, with no persistent daemon. New outbox entries kick
dispatch after commit; bounded batches continue until drained and native broker
delay wakes retries and lease reconciliation without holding Functions open.
Exam attempts schedule their expiry. Hourly maintenance retains deadline reminders,
expiry fallback, orphan upload cleanup and outbox recovery. It queues its successor
before work and uses a database deployment fence to stop older timer chains.
Successful API traffic or `/ready/` activates the runtime through its canonical
alias. Readiness probes both queues end to end, including the actual OCR engine.

Vercel's queue dispatcher invokes synchronous subscribers from an async loop.
The Vercel-specific Django task base uses Celery's documented `Task.Strategy`
extension to move the complete inline task lifecycle to one synchronous thread
when such a loop is present. This includes Django's prerun/postrun database
cleanup, keeps ACK/retry ordering and request context variables, and preserves
serial solo-worker execution. Normal worker threads retain Celery's default
strategy. Django's async safety guard remains enabled.
The worker entrypoint imports tesserocr before starting task discovery. Its
cysignals dependency installs signal handlers on first import and therefore must
initialize on the entrypoint's main thread, before OCR tasks use the sync thread.
The cold-start regression imports the actual native module after worker startup
from a task thread; strategy tests use the real Celery solo pool and task signals.

Embedded OCR uses pinned Tesseract wheels and checksum-pinned official tessdata_fast
assets for Russian, Kazakh and English, initialized in private storage. Long
extraction yields between pages, retaining unpublished staging in PostgreSQL, then
publishes all immutable citation chunks atomically. Existing page, byte, character,
per-page OCR and total extraction limits remain in place.

Direct uploads retain the 25 MiB limit. Five-minute signed POST grants constrain a
random quarantine key, exact length and MIME after user/target authorization.
Single-use database tickets bind owner, endpoint, method, field and exact form
context. Django reads a bounded private object, verifies actual metadata/content
using the existing validators, then saves a new immutable private file. Original
endpoint business permissions run again. Maintenance removes expired quarantine
objects. XLSX imports and local/Docker multipart transport remain unchanged.

Authorized downloads redirect to 60-second signed attachments or validated image
previews. The bucket stays private. Backend build preparation configures exact
CORS origins and tests a real 25 MiB POST, signed range download and denial of
anonymous access, deleting the probe in all cases. The Vercel frontend build
enables this transport. `config.vercel_build` then loads strict production settings,
applies forward migrations, runs release preflight/deployment checks, collects
static assets and initializes the readiness sentinel. Missing SMTP or other
production settings still stop the build; development settings are never used.

Free quotas still apply. No paid upgrade or unlimited free operation is promised.
Initial administrator access and any intended AI provider key/model/budget must
be supplied and verified before reporting every feature as available. AI remains
disabled; manual course creation and uploads remain available.

Validation before the final runtime fixes: GitHub CI passed all 322 backend tests,
including PostgreSQL concurrency, all 43 frontend tests, browser acceptance,
container checks and dependency audits. Actual embedded OCR recognized a combined
Russian/Kazakh/English sample. Cloud build acceptance verified a real 25 MiB
private upload, signed range download and anonymous object denial. The final
template and synchronous-strategy fixes passed all 318 local backend tests
(8 PostgreSQL-only checks skipped locally), including real ORM queries in Celery
task signals under an async dispatcher. Cloud verification and CI on the final
candidate remain release checks. The Docker scan exposed five fixable frontend
findings and an expired review of known, unfixed Debian findings; the frontend
packages and scoped native review were refreshed without changing the scan gate.
See `SECURITY_REVIEW.md` for residual native-library limits and demo scope.

Acceptance must cover: health/readiness, admin/teacher/student login and roles,
course creation and assignment, large-file upload and private download, tests and
grades, data persistence after a redeploy, SMTP delivery, background execution,
and anonymous access to the approved public site URL.

## References

- https://vercel.com/docs/frameworks/full-stack/django
- https://vercel.com/docs/headers/request-headers#x-forwarded-for
- https://vercel.com/docs/services/config-reference
- https://vercel.com/docs/daemons/config-reference
- https://vercel.com/docs/errors/function_payload_too_large
- https://vercel.com/pricing
