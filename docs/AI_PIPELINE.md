# AI pipeline

Upload validates extension, claimed MIME, file signature/structure and configurable size. Storage keys are random UUIDs. Office archives reject macros and excessive decompressed size. Documents are private and course scoped.

Celery extraction loads PDF text first; short/empty pages use Tesseract OCR. Images use OCR. DOCX paragraphs/tables and PPTX text frames are extracted. Whitespace is normalized; bounded chunks retain document, page/slide/section and index. Extraction errors are persisted without document text or secrets in logs. Source limits and worker hard/soft timeouts bound processing.

Generation is requested only after all sources finish. It receives bounded chunks with IDs, language, complexity, week count and assessment flags. A provider abstraction owns OpenAI SDK calls. `responses.parse(..., text_format=CourseDraft)` uses Pydantic structured outputs; refusals, truncation, invalid answer options, wrong week counts and fabricated/foreign citations fail validation. Source content is explicitly untrusted data, not instructions. See the [official Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs).

The source-only prompt reduces hallucinations but cannot prove factual correctness. Teacher review is mandatory. Source gaps are displayed. Teachers edit title, description, weeks, topics, assignments, questions and answer options, reorder/remove/add elements, and request regeneration of a selected topic. Regeneration preserves the original draft and returns a new one. Save edits before confirmation; imported drafts are frozen.

Confirmation creates a new editable CourseVersion in one transaction. It preserves chunk IDs on generated content, creates text materials and initializes grading components from generated assessments. Content-only drafts require the teacher to add an assessment/grading scheme before publication. The ordinary publication service validates everything again. Students cannot access jobs, sources, chunks or drafts.

Only rate limits, connection/timeouts and provider 5xx are retried (one retry by default with exponential backoff). Other errors fail immediately. Cancellation prevents import of a completed provider response but cannot retroactively cancel provider billing. Token usage and duration are logged. Generation is blocked unless per-million input/output prices are configured. A transactional application-wide daily budget reserves cost before each call; see [cost controls](AI_COSTS.md). Daily job quotas and request throttles limit usage; also configure the provider's account/project budget.

Worker availability and stale QUEUED/PROCESSING records must be monitored in production. Redis messages carry IDs; email payloads are encrypted in the database and never sent as plaintext task arguments. Real provider/Redis/OCR/S3 tests are deployment acceptance gates, separate from mocked unit tests.
