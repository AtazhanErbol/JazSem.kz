# Backup and restore

Set retention, RPO and RTO according to the institution's policy; no legal retention period is assumed. A practical starting operational schedule is daily logical DB backup plus provider-managed point-in-time recovery, with storage versioning and a separate encrypted backup account. Document the approved schedule before launch.

PostgreSQL: `pg_dump --format=custom --file=jazsem.dump "$DATABASE_URL"`. Run from a trusted backup runner with credentials in environment/secret manager. Encrypt the dump, checksum it and move it to a separate private backup location. Back up roles/grants separately with appropriate privileges. Do not put dumps into Git.

Object storage: enable versioning, replicate to a different account/location and test restore of both current and deleted object versions. A bucket mirror alone is insufficient if deletions also propagate. Retain the DB snapshot and matching object versions. Back up MAIL_ENCRYPTION_KEY and Django secret securely with access independent from the application host. Redis is a broker/cache, not the authoritative learning store; use durable Redis persistence and inspect/reconcile pending jobs after recovery.

Restore rehearsal:

1. Restore into an isolated environment, never overwrite the running production DB without a separately approved recovery procedure.
2. Provision empty PostgreSQL; run `pg_restore --no-owner --dbname="$RESTORE_DATABASE_URL" jazsem.dump` with compatible roles.
3. Restore private object versions and encryption keys. Point isolated configuration at restored services. Disable outgoing email and provider calls during validation.
4. Verify migration state, account counts, enrollments, published versions, grades, files and permissions. Test one authenticated download and a full learning path.
5. Reconcile unsent email and queued AI jobs to avoid unintended duplicate external effects. Resume worker/beat only after reconciliation.
6. Record restore duration, restored timestamp, discrepancies and operator. Repeat periodically and before major upgrades.

Orphan uploads: run `python manage.py orphan_uploads --manifest /secure/review/orphans.json` to create a dry-run manifest for unreferenced `private/` keys older than 72 hours (minimum permitted grace: 24 hours). Review it before `--apply` with the same manifest. Apply rechecks age and references across every material/version, submission and source; shared storage keys are preserved. Never run during DB restore or while an external process is attaching historical keys. S3 object version retention follows the bucket policy; this command does not purge historical object versions. No cleanup has been executed against production. Existing materials receive nullable metadata in `materials.0002_file_metadata`; new/replaced files record their actual download name, MIME and size, without reading old objects during migration.
