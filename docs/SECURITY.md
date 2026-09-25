# Security model

Backend authorization is mandatory regardless of frontend routes. Teacher queries are scoped by ownership; all parent foreign keys are checked. Student content queries bind the exact enrollment version and published course/version state. Student serializer output removes correct-answer flags, explanations and AI citations. Submissions, attempts, grades, notifications and files are scoped independently.

Session cookies are HttpOnly/SameSite=Lax; production adds Secure and HTTPS/HSTS. CSRF covers login, password reset and authenticated mutations. Password validation uses Django, temporary credentials use cryptographic randomness, reset tokens expire and are invalidated by password change. Inactive accounts cannot authenticate. Existing roles cannot be changed through generic updates, preventing accidental reinterpretation of historical ownership. Administrator provisioning uses createsuperuser or admin account creation API.

Published content is frozen; mutation and publication share row locking on the version. Enrollment, assignment submission and test-attempt allocation lock parent rows and use unique database constraints. PostgreSQL is required to verify concurrent writes: SQLite tests do not validate row-lock behavior. Grading and AI import are atomic, audit records are append-only through the API, and duplicate import/finalize/submit calls are idempotent.

Uploads are limited by extension, MIME, signature, maximum size and Office archive expansion. Storage names never use user paths. Private download responses use attachment disposition, nosniff and no-store. The platform does not render arbitrary uploaded HTML or execute uploaded files. React escapes content; Nginx CSP restricts scripts to same origin. Malware scanning and content-disarm can be added at the upload boundary before institutions accept untrusted external documents; no claim of antivirus protection is made.

SMTP payloads are encrypted at rest until delivery, then cleared. Celery receives identifiers only. API responses, audit fields and application errors exclude password/token/API-key fields. Development console email intentionally prints email contents and must never be enabled in production. Avoid debug logging of SDK requests or full task arguments. Sentry uses no default PII.

Rate limits protect login, reset, upload and AI generation. Redis provides shared counters in production; add edge limits for network-level abuse. Daily AI job quotas and provider-side billing controls are separate layers. Source text is treated as untrusted data; schema/citation checks do not establish factual truth, so human review is required before publication.

Before release: run PostgreSQL concurrency/integration tests, dependency audits, authorized security review, private bucket checks, cross-role E2E and backup restore. Keep production services on a private network; the TLS edge is the only ingress. Restrict access to logs, backups and encrypted mail keys.
