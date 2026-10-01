# Release upgrade and rollback

Current evidence and approval status: [RELEASE_CANDIDATE](RELEASE_CANDIDATE.md). Production Compose is `infra/compose.production.yml`; it uses managed PostgreSQL, authenticated Redis and private S3, not the development MinIO. It does not provision TLS, IAM, backups or monitoring. Building/testing does not authorize deployment or traffic.

## One upgrade order

Use the **new matching application image** for management commands, with the target configuration injected by the operator. Never print `.env` or secrets. Below, `manage` means `docker compose -f infra/compose.production.yml run --rm --no-deps backend python manage.py`. Inspect `showmigrations --plan` first; target migrations below are only for genuinely older schemas, never commands to reverse an already newer schema.

1. Build/pin reviewed images and check configuration with `manage check --deploy`. Inspect migration state. Perform a read-only `manage release_preflight` before changing data. It prints counts, not records, and fails without repairing anything.
2. **Legacy schema before RC ownership/mail columns:** run `manage release_preflight --legacy`. Only missing `accounts.User.owner_teacher` and `notifications.MailOutbox.status` in existing tables are deferred; other missing schema is an error. Known state/course/version conflicts must be resolved explicitly before proceeding. Do not apply all constraints before this check.
3. Take a verified database/object/key backup, then place the application in maintenance and stop all writers and old workers/beat. Take a final quiesced recovery snapshot (or record its equivalent PITR/object version boundary). Do not mix old and new AI/mail workers.
4. On a legacy schema only, apply the still-missing additive migrations in order: `manage migrate accounts 0003_student_owner_teacher`, `manage migrate ai 0003_durable_generation`, `manage migrate notifications 0002_delivery_leases`. These existing migrations preserve history, but retire unsnapshotted active legacy AI jobs as uncertain rather than replaying possible charges. Teacher-created student ownership is copied by the historical migration; admin-created students need explicit ownership review. This release introduces **no new migrations** and does not rewrite those historical files.
5. Run full `manage release_preflight` with no deferred fields. Any ownership conflict is an operator/data-owner decision; never auto-reassign or delete enrollments to pass. Then `manage migrate --noinput` for the remaining constraints/correlation/metadata migrations; run preflight and system check again.
6. Initialize the private sentinel once with `manage storage_probe --initialize`. Verify private access independently. Start matching API, short (`celery` service), `heavy`, one `beat`, and `web` using production Compose. App/worker/web containers run non-root, read-only, with `/tmp` writable, all capabilities dropped and no-new-privileges.
7. Verify `/health/` and `/ready/`, HTTPS Host/CSRF/secure cookies, private upload/download, queues and recovery, admin → teacher → student workflow. Complete target SMTP, storage, monitoring and restore gates. Route traffic only after the owner's separate release decision.

**Empty installation:** absence of all tables is not an accepted legacy schema. Preflight returns structured missing-schema metadata rather than a SQL error. Verify the database is intentionally empty, run `migrate --noinput`, full preflight, `createsuperuser`, sentinel, then startup/smoke. Never seed production. **Already at a712f64:** full preflight, backup/quiesce, normal forward `migrate`, full preflight; do not run old migration targets.

## Transport and proxy contract

Production network: `172.30.0.0/24`, gateway `.1`, API `.10`, web `.20`. Check conflicts; changing addresses requires coordinated Compose/Nginx/TRUSTED_PROXY_CIDRS changes. The trusted TLS edge in `infra/tls-edge.conf` overwrites client IP/proto headers; web accepts the normalized client address only from that edge; Django accepts verified forwarding only from web. Backend has no published port, web binds host loopback. Configure a real additional CDN/load-balancer chain explicitly; never trust arbitrary XFF. The acceptance lab uses a distinct trusted edge `.30` and two real client addresses to test this boundary.

Configure explicit hosts, HTTPS FRONTEND_URL, exact CSRF origins, PostgreSQL (prefer `sslmode=verify-full`), authenticated Redis TLS and CA, private S3 transport/IAM, SMTP STARTTLS or implicit TLS (not both), and mail encryption keys. `TRUSTED_SERVICE_NETWORK=true` permits plaintext service traffic only inside an independently verified private service network; it is not TLS/IAM certification. Rediss options require CA/hostname verification in cache, actual Celery broker and result clients. Bucket names do not prove privacy, versioning or encryption.

Keep AI disabled during rollout. A live small-sample call requires separate consent with model, price, budget and quality criteria; it is not part of these commands. Real inbox delivery and target-domain TLS are external gates even after the local sink and lab CA pass.

## Rollback

Rollback only to a recorded **schema-compatible application digest**. Preserve new migrations, ownership, old enrollments/versions, attempts/grades, draft citations, uncertain AI reservations and encrypted mail. Ownership data migrations intentionally have no reverse data rewrite; schema rollback loses state/lease semantics. Stop incompatible writers/consumers before switching. Restore backups into a separate environment first; replacement of live data requires a separately approved recovery plan. No automatic destructive rollback, reverse migrations, old workers or traffic switch is authorized by this runbook.

## Reproducible isolated acceptance

The ordered commands are executable in `.github/workflows/ci.yml`, jobs `browser`, `production-runtime`, `secrets`. Use a fresh disposable lab: `python scripts/acceptance_prepare.py`, Compose build/dependencies/migrate, `acceptance_phase.py init`, app startup, `tls`, `http`, `acceptance_infrastructure.py`, isolated fake-provider overlay, `acceptance_faults.py`, `acceptance_restore.py`, `acceptance_extras.py`, `acceptance_proxy.py`, `scan_acceptance_images.py`. Set `RC_SOURCE_REF` to the exact tested commit. Only the fixed `jazsem-acceptance` project may be destroyed between runs. Its control fixtures and restored database intentionally reject reuse; preserve safe evidence first.
