# JazSem on Vercel

## Current state

The `vercel-deploy` branch contains the initial deployment configuration.
`codex/vercel-deploy` contains the candidate Vercel proxy adapter and tests in
draft PR #1; synchronize it to the deployment branch after configuring and
verifying the runtime services. The main branch is unchanged.

- React and Django build successfully on Vercel after declaring the locked Python
  runtime dependencies in `backend/pyproject.toml`.
- The landing page and login form render in the preview.
- The backend is not operational until production environment variables and
  external services are connected. Do not report the complete app as deployed.
- `jazsem.vercel.app` has no production deployment yet. Preview access is protected
  by Vercel Authentication. Public production promotion still needs authorization.

## Runtime and security

`tool.vercel.entrypoint` uses `config.vercel_wsgi:application`. This entrypoint
requires `VERCEL=1`, production settings, and the fixed in-process trusted peer
`127.0.0.1/32`. It adapts Vercel's documented, edge-overwritten X-Forwarded-For
header into the existing trusted-proxy contract. It rejects missing, ambiguous,
or invalid edge headers before Django and ignores caller-supplied private-proxy
headers. The standalone Docker deployment still uses `config.wsgi`.

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
Application encryption keys, environment-specific frontend/CSRF origins and
SMTP configuration are still pending. Migrations have not been run.

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
--initialize`. Production must not use `seed_dev`.

The existing application needs three persistent background processes: the short
Celery worker, heavy Celery worker with OCR dependencies, and exactly one beat
scheduler. Use the same backend source/image and production configuration as the
API. Workers must set `WORKER_ROLE=short` / `heavy` for readiness heartbeats.
Vercel Daemons can run these Docker processes; they have not yet been provisioned
or enabled. Keep them stopped until their services and credentials are ready.

Two platform constraints need resolution before claiming full parity:

1. The existing upload API accepts files up to 25 MiB, whereas Vercel Functions
   limit request bodies to 4.5 MB. Implement authorized, validated direct uploads
   to private object storage, or choose a backend runtime that supports these
   requests. Do not silently lower the application's stated limit or make the
   bucket public.
2. Hobby has finite daemon memory-hour allowances. Three always-running workers
   cannot be assumed to remain within the free allowance for a full month.
   Confirm a sustainable worker arrangement or demonstrate explicit on-demand
   operation before promising a permanently available complete free deployment.

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
