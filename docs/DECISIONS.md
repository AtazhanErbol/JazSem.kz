# Decisions

- Same-origin session authentication minimizes browser credential exposure; CSRF also applies to login/reset POSTs.
- Locale code `kk` is standards-compliant Kazakh; the language selector displays KZ.
- One owning teacher per student in release 1; group/course assignment requires matching ownership. Admin can manage all.
- A published version is frozen. New enrollments use the current version; existing enrollments never silently migrate.
- One student/course enrollment for life in release 1. Retakes require an explicit future migration policy.
- Grades stored/displayed as percentages. Missing work contributes zero to component means. Best graded test attempt counts; latest graded assignment attempt counts. Passing thresholds do not determine content progress.
- Private files are authenticated downloads with attachment disposition and nosniff, including when S3 is configured.
- Mail credentials are encrypted in a database outbox using a dedicated environment key. Tasks receive only row IDs; successful delivery clears content. SMTP cannot guarantee exactly-once delivery after a worker crash.
- No organization contacts, legal claims or model prices are invented. Public CMS and environment configure them.
