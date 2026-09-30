# Persisted states and concurrency — RC, 2026-09-30

The RC migrations add choices and CHECK constraints after a read-only `python manage.py release_preflight`. A nonzero count is a migration blocker: investigate rows in an authorized environment; do not silently coerce states or delete history. The command checks enrollment/version course identity and ownership, which cannot be expressed as a cross-table SQL CHECK. Existing schema migrations remain intact.

| Entity | Real transitions | Authority / history |
|---|---|---|
| Course | DRAFT → PUBLISHED → ARCHIVED; a later version can be published | Author/admin service; generic status patch forbidden |
| Version | DRAFT → PUBLISHED; legacy REVIEW remains editable → PUBLISHED | Published content immutable. Copy creates DRAFT, existing enrollments retain their version |
| Enrollment | ASSIGNED → IN_PROGRESS → COMPLETED | Learning actions; progress is completion, not a passing score. Historical ARCHIVED/FAILED stay readable; no new generic transition API |
| Submission | SUBMITTED/RESUBMITTED → UNDER_REVIEW → GRADED or REVISION_REQUESTED | Revision creates a new numbered submission on resubmit. Regrade allowed and audited. Latest graded submission determines grade |
| TestAttempt | IN_PROGRESS → GRADED or EXPIRED | Server clock and server answer set; terminal attempts never reopen; best graded/expired score counts |
| AIJob | QUEUED → PROCESSING → COMPLETED/FAILED; QUEUED/PROCESSING → CANCELLED | Course lock and one-active-job constraint. Safe stale pre-provider execution can return to QUEUED; uncertain provider outcome stays failed and reserved |
| Source | QUEUED → PROCESSING → COMPLETED/FAILED; FAILED → QUEUED by explicit retry | Completed chunks immutable. Exclusion is separate from state, citations retained |
| Mail | PENDING/RETRY → SENDING → SENT/RETRY/FAILED; FAILED → PENDING by admin | Short claim + expiring lease, token-fenced finish, encrypted until sent. Uncertain SMTP can duplicate |

Lock order: group (when applicable) → all affected courses sorted by PK → student; course → version → editable content; enrollment → attempt. Content mutation, publication and copy share course/version serialization. Group join locks all inherited courses before its student; group assignment visits students in PK order. Owner changes lock the student and reject conflicting historical ownership. Mail claims never hold a database transaction over SMTP.

PostgreSQL tests use separate connections and barriers/events for last-admin protection, enrollment idempotency, group assignment/join, publication/edit, start/expiration, AI uniqueness, budget and mail claims. SQLite skips are not evidence of locking. The recorded start/expiration deadlock was reproduced on PostgreSQL before its fix (RELEASE_CANDIDATE.md).

Rollback: these constraints preserve data. Prefer a compatible application rollback; do not deploy old unsnapshotted AI workers over durable queued jobs. Stop workers before the AI migration, run preflight before the state migrations, migrate once, initialize the storage readiness sentinel, start both short/heavy consumers and beat, then route traffic after readiness. Apply historical migrations to a synthetic copy before staging rollout. Production/staging data checks and restore remain release gates.
