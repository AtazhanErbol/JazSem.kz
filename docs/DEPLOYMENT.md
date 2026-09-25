# Production deployment

Use a dedicated Linux host or equivalent container runtime, managed PostgreSQL 16+, Redis with private network/authentication, and a private S3-compatible bucket. Production Compose is `infra/compose.production.yml`; it does not provision managed dependencies or TLS. Development Compose is not a production security profile.

Development/CI builds MinIO from the fixed official source tag `RELEASE.2025-04-22T22-12-26Z` because the previously published registry images are unavailable. The [community repository](https://github.com/minio/minio) is archived; this isolated development service is not a recommendation for a new production storage deployment. `init_dev_storage` creates a private bucket and is blocked when DEBUG=False. Use a maintained S3 service for production and review dependency/image security as part of every release.

1. Create database/user with least privileges; enable encrypted connections and backups. Configure authenticated private Redis and durable broker storage.
2. Create a private S3 bucket and credentials limited to that bucket. Enable encryption, versioning and lifecycle policies. No anonymous read policy. Downloads are streamed by Django after permission checks; no public media location in Nginx.
3. Prepare `.env` outside source control. Set production SECRET_KEY, MAIL_ENCRYPTION_KEY, DATABASE_URL, REDIS_URL, S3 fields, SMTP/TLS credentials, allowed hosts, frontend HTTPS URL and exact CSRF trusted origins. Keep CORS empty for same-origin hosting. Configure OpenAI model/key and billing budget. Rotate any development credentials.
4. Build: `docker compose -f infra/compose.production.yml build`.
5. Backup existing DB, then run migrations once: `docker compose -f infra/compose.production.yml run --rm backend python manage.py migrate --noinput`.
6. Create the first administrator: `docker compose -f infra/compose.production.yml run --rm backend python manage.py createsuperuser`. Never run seed_dev in production.
7. Start services: `docker compose -f infra/compose.production.yml up -d`.
8. Put a trusted TLS edge in front of `127.0.0.1:8080`. Backend has no public port. Nginx sets `X-Forwarded-Proto: https`; never expose this trust boundary directly to an untrusted network. Proxy Host must preserve the public domain. Redirect HTTP to HTTPS at the edge.
9. Run `python manage.py check --deploy --settings=config.settings.production`. Verify health/readiness through the public domain, secure session/CSRF cookies, SMTP delivery, upload/download, OCR language packs, worker/beat and a real OpenAI draft followed by review/publication.
10. Complete an end-to-end admin → teacher → student run on production-like staging, load tests, security review and restore rehearsal before exposing real student records.

Run one beat scheduler, scale workers/API separately. Monitor queue age, failed jobs, unsent MailOutbox rows, 5xx/429 rates, storage/DB capacity and provider usage. SENTRY_DSN is optional; no default PII. Logs include request IDs; AIJob retains originating request_id. Match upload limits at edge, Nginx and Django. Worker filesystem has only temporary writable space; use S3 for durable uploads.

Updates: pin image versions/digests in your release process, build from lockfiles, run CI, backup, apply reviewed migrations and deploy. Never automatically roll back a destructive database migration. Roll back application images only when schema compatibility is established. Keep key history available until encrypted pending mail is sent or explicitly discarded.

External infrastructure, DNS, TLS certificates, production keys and commercial/legal data are intentionally environment-owned. This repository does not certify a live deployment until the above acceptance gates are run.
