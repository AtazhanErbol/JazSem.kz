# JazSem.kz architecture

Modular monolith: Django/DRF owns authorization and transactions; React/TypeScript consumes `/api/v1/` through TanStack Query. PostgreSQL is authoritative. Redis serves Celery and throttling. Private S3 objects are only streamed after authorization. Nginx serves the SPA and proxies the same-origin API; no tokens in browser storage. Sessions are HttpOnly, CSRF protected, rotated on login, invalidated by password changes.

## Domain boundaries

accounts: custom users, ownership of students, password lifecycle. academics: disciplines, teacher assignments, groups and membership history. courses: immutable published versions and editable drafts, weeks and topics. enrollments: one enrollment per student/course with multiple provenance records. materials: private validated uploads. assignments: submissions and revision history. testing: server timers, stable shuffle, autosaved answers and exact-set marking. grading: version-bound weighted components. progress: activity completion independent of grades. ai: extraction, citations, typed generation, human review and transactional import. notifications: in-app events and encrypted mail outbox. audit: append-only business events. cms: configurable public content. common: API errors, permissions and observability.

## Permission matrix

Admin manages all. Teachers manage only their courses, assigned disciplines, groups and owned students. Students read only published versions pinned by their own active enrollments, submit only their own work, and read only their own results. Querysets enforce scope before lookups; all foreign-key inputs are checked against that scope. A temporary-password session can access only self, logout and password change. No role or owner comes from untrusted mutation payloads.

## State machines

Course: DRAFT → PUBLISHED → ARCHIVED. Version: DRAFT → REVIEW → PUBLISHED → ARCHIVED. Published content is immutable; duplicate into a new draft to change it. Publishing validates nonempty topics, question correctness and a 100% grading scheme. Existing enrollments keep their version.

Enrollment: ASSIGNED → IN_PROGRESS → COMPLETED; administrators may archive. Unique (student, course) prevents parallel duplicate learning. Group assignment is transactional, membership additions inherit active group courses. Source records retain group and individual provenance.

Submission: SUBMITTED → UNDER_REVIEW → GRADED or REVISION_REQUESTED → new RESUBMITTED attempt. Prior attempts persist. Lock the enrollment before allocating attempt numbers. Duplicate submit returns current attempt. Test: IN_PROGRESS → GRADED/EXPIRED. Server checks expiry on every save/finalize; scheduled expiry handles idle sessions. Correct answers never appear in student serializers.

AI: QUEUED → PROCESSING → COMPLETED/FAILED/CANCELLED. Extraction creates source chunks with page/slide references. Generation uses validated structured output. Drafts are private. Confirmation imports into an editable version; publishing is a separate validated action. Retry only transient provider failures, with bounded backoff. Redis carries identifiers, never plaintext credentials.

## Frontend / UX

One role-aware shell, localized RU/KK translation keys, accessible forms and explicit pending/error/empty/success states. Calm graphite/white application with red accent. Landing uses the same tokens. Course tree and content pane collapse on mobile. Builder and AI wizard use real mutation endpoints and require confirmation before publishing. Server state invalidation follows successful mutations. React escapes text; no raw HTML rendering.

## Infrastructure / delivery

Development Compose: PostgreSQL, Redis, MinIO, API, worker, beat, frontend. Production: separate nonroot images, TLS at trusted edge, durable object/database volumes, explicit migration job, health/readiness, structured logs with request IDs, optional Sentry. Credentials, model, pricing and organization information are configurable. CI checks lint, types, build, tests and migration drift. Release requires real service integration and restore rehearsal; unit tests alone do not certify production readiness.
