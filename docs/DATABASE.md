# Database contract

All timestamps are aware, stored in UTC. IDs are UUIDs except Django infrastructure. Foreign keys use PROTECT for historical records. Deactivate/archive users and domains instead of deleting learning history.

User (unique case-insensitive email, username, role, preferred_language, must_change_password, created_by) → StudyGroup.teacher / Course.teacher. Discipline ↔ teachers via explicit assignment. GroupMembership(group, student, joined_at, left_at, status) has a conditional unique active membership. A student has one owning teacher in release 1; reassignment requires administrative workflow.

Discipline → Course → CourseVersion(unique course, number) → Week(unique version, number) → Topic → Material, Assignment, Test → Question → AnswerOption. Current published version is explicit on Course. Published trees cannot be edited. Provenance stores source chunk IDs for generated topics, assignments and questions.

Enrollment(unique student, course) pins CourseVersion. EnrollmentSource records INDIVIDUAL or group provenance; GroupCourseAssignment(unique group, course) drives current/future memberships. Source removal does not silently delete historical learning.

Submission(unique assignment, student, attempt_number) → SubmissionFile; scores constrained to 0–100, normalized from activity maximum. TestAttempt(unique test, student, attempt_number; at most one in progress) contains stable order and deadline. TestAnswer(unique attempt, question) contains selected option IDs. Services validate option ownership and exact-set marking.

GradingScheme one-to-one version → GradingComponent(kind, weight). Services validate sum=100 and applicable content before publication. StudentProgress(unique enrollment, material) stores explicit material completion; assignment/test completion derives from persisted submission/attempt state. Progress reports and grade aggregates remain separate.

SourceDocument → DocumentChunk(unique document, chunk index). AIJob references requesting user/course and draft. AICourseDraft stores schema-validated JSON and imported version; one import per draft. AIUsageLog records tokens, configured cost, duration and status. AuditLog excludes secrets. Notification recipient-scoped. Encrypted email outbox deletes body after successful dispatch.

Indexes: foreign keys automatically, role/status on users, domain status, submission status+time, AI status+time. PostgreSQL constraints are the final protection for concurrency; services use atomic blocks and select_for_update on parent enrollment/course/group/user rows.
