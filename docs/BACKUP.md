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

## Recorded synthetic rehearsal

`python scripts/acceptance_restore.py` runs only on the fixed acceptance project after its fault fixtures. It quiesces API/short/heavy/beat, snapshots all models including auto-created membership tables, `pg_dump -Fc`, copies matching private objects by SHA-256, restores into a new `jazsem_rc_restore` database and `jazsem-acceptance-restored` bucket, then verifies complete model fingerprints, owner/creator, old enrollment version, grades/progress/attempts, AI citations, mail decryption and a scoped authenticated private download. The download uses Django's in-process session HTTP client; live HTTPS is separately covered by acceptance_phase.py.

Durations, counts and limits: [restore evidence](measurements/restore.json). This is a quiesced synthetic rehearsal, not recovery of production backups or a production RPO/RTO/SLA. `acceptance_extras.py` also runs real S3 orphan dry-run/apply with a deliberately advanced 96-hour command clock and stopped writers; it preserves shared-version references, a newly attached reference and the sentinel. No real user bucket was cleaned.

Use the common upgrade/rollback ordering in [DEPLOYMENT](DEPLOYMENT.md). Keep encrypted backups and old mail keys outside source control with tested access/retention; those target policies remain to be provided by the owner.
