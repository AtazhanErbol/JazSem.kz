# Encrypted mail delivery and recovery

Mail is queued transactionally with account/reset/notification changes. A worker claims one row in a short transaction, commits, sends outside database locks, then records the result only if it still owns that lease. Beat runs the dispatcher each minute. Five attempts per retry cycle use exponential delay (30 seconds up to one hour); all attempts remain counted. Authentication, permanent recipient/DATA 5xx and decryption failures require operator action immediately. SMTP 4xx (including recipient refusal) is transient; SMTP_PERMANENT_FAILURE is localized in RU/KK. Expired claims are recovered; the final expired attempt becomes FAILED.

ADMIN → Management → Mail delivery shows status, recipient, timestamps, attempt counts and a fixed error code. No subject, body, encrypted payload, password or reset token is exposed. Fix the reported configuration, then use Retry. Active/SENT deliveries cannot be retried. Retries are audited. `GET /api/v1/mail-outbox/metrics/` gives counts and oldest unsent age for an authenticated administrator.

SMTP does not offer exactly-once delivery. A worker can die after the mail server accepted a message and before the database records SENT. Lease recovery may send a duplicate; reset tokens still retain expiry and single-use behavior. Do not report SMTP acceptance as proof that Gmail placed mail in an inbox.

## Key rotation

1. Retain the old key securely with backups. Configure a new `MAIL_ENCRYPTION_KEY` and add previous keys to comma-separated `MAIL_PREVIOUS_ENCRYPTION_KEYS`. Do not put keys in tickets, logs or git.
2. Deploy the same key set to API and workers. Run `python manage.py rotate_mail_keys` to validate queued messages (dry run).
3. Run `python manage.py rotate_mail_keys --apply` to re-encrypt remaining payloads with the primary key. Output contains counts only. A nonzero exit means some queued messages cannot be decrypted; keep the old keys and investigate before retrying.
4. Remove old keys from active runtime only after validation, keeping the matching keys available for restoring older backups. Successful sends clear ciphertext.

## Migration and rollback

`notifications.0002_delivery_leases` classifies already sent mail as SENT and old exhausted mail as FAILED; it preserves unsent ciphertext and attempt counts. Stop old mail workers before migration, then start the matching new workers. Roll back the application only to a release that understands these delivery states. A schema rollback cannot preserve retry/lease semantics; never mix old and new workers.

Local verification uses locmem/file mail sinks. Regression tests cover delivery outside transactions, deferred retries, admin visibility/permissions, lease recovery, no repeat after SENT, missing keys and rotation. PostgreSQL competing claims are part of the full suite. `acceptance_faults.py` uses a real local STARTTLS SMTP sink: 451 retries with backoff then sends, 550 fails once for operator action, invalid ciphertext is retained and fails once. The exact source/evidence is recorded in RELEASE_CANDIDATE.md. Actual Gmail delivery/inbox placement remains an external gate.

Upgrade order is canonical in [DEPLOYMENT](DEPLOYMENT.md); do not apply mail migrations while legacy workers can write.
