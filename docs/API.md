# API v1

Base: `/api/v1/`. Same-origin HttpOnly session cookies. First GET `/auth/login/` obtains `csrfToken`; every unsafe request sends `X-CSRFToken`. Login rotates the CSRF cookie: obtain a fresh token afterward. No bearer token/localStorage authentication. Content type JSON except file uploads (multipart). Private downloads require the same authenticated session.

Errors: `{code, message, errors}` with appropriate 400/403/404/409/429/500. Permission-filtered objects return 404. Login/reset responses do not return credentials or account existence. Temporary-password users can only access self, logout and password change.

## Identity

- `POST auth/login/`: email, password; returns current user.
- `GET/PATCH auth/me/`: read profile; patch first_name, last_name, preferred_language only.
- `POST auth/change-password/`: current_password, password.
- `POST auth/forgot-password/`: email; generic response.
- `POST auth/reset-password/`: uid, token, password. Token expires and is invalid after password change.
- `POST auth/logout/`.
- `GET/POST/PATCH users/`: admin creates teachers/admins/students; teacher creates owned students only. Creation queues encrypted temporary credentials. `POST users/{id}/deactivate/` blocks access. Role migration is intentionally disallowed for existing users.

## Academic / authoring

List/detail/create/patch resources: disciplines, groups, courses, weeks, topics, materials, assignments, tests, questions, options, grading-schemes, grading-components, content. Delete only draft content children; historical entities use archive/deactivate.

Parent IDs: weeks.course_version, topics.week, materials/assignments/tests.topic, questions.test, options.question, grading-schemes.course_version, grading-components.scheme. Parent reassignment is disallowed. Foreign IDs are scoped before mutation.

- `GET courses/{id}/versions/`: teacher's versions; student only enrolled published versions.
- `GET courses/{id}/tree/?version=UUID`: nested content. Students always receive their pinned version and never question answer keys.
- `POST courses/{id}/publish/`: `{version}`. Validates content, question options and total grading weight.
- `POST courses/{id}/duplicate/`: `{version}` → new draft.
- `POST courses/{id}/assign/`: `{student}`.
- `POST groups/{id}/assign/`: `{course}`; creates enrollments for active members.
- `GET/POST groups/{id}/members/`: POST `{student}`; new member inherits active assignments.
- `POST groups/{id}/remove-member/`: `{student}`; preserves history.
- `POST courses|groups|disciplines/{id}/archive/`.

## Learning / assessment

- `POST materials/{id}/complete/`, `POST topics/{id}/complete/`: explicit reading completion.
- `GET materials/{id}/download/`, `GET submission-files/{id}/download/`: authenticated attachments, private cache headers.
- `POST assignments/{id}/submit/`: text_answer plus optional repeated multipart `files`. Duplicate click returns current attempt; revision creates the next attempt.
- `GET submissions/`: paginated, filter status/assignment/student, search email/title.
- `POST submissions/{id}/start-review/`.
- `POST submissions/{id}/grade/`: `{score,comment}`. Score is raw activity points, normalized to 0–100 on storage.
- `POST submissions/{id}/request-revision/`: `{comment}` required.
- `GET submissions/{id}/files/`.
- `POST tests/{id}/start/`: resumes active attempt or allocates one atomically.
- `GET attempts/{id}/`: persisted ordering, choices, saved answers and server_time.
- `POST attempts/{id}/answer/`: `{question,selected_options:[UUID]}`. Rejects foreign choices and expired attempts.
- `POST attempts/{id}/finish/`: idempotent marking. Exact set match; no partial credit.
- `GET enrollments/{id}/progress/`: activity completion, independent of score.
- `GET enrollments/{id}/grades/`: weighted component scores.

## AI / operations

- `POST sources/`: multipart course/file. Returns immediately; Celery extracts text.
- `GET sources/?course=UUID`, `GET sources/{id}/chunks/`, `GET chunks/{id}/`.
- `POST ai-jobs/`: course, weeks (1–16), language (ru/kk), complexity, assignments, tests.
- `GET ai-jobs/{id}/`, `POST ai-jobs/{id}/cancel/`, `GET ai-jobs/{id}/draft/`.
- `PATCH ai-drafts/{id}/`: `{data: validated course structure}`.
- `POST ai-drafts/{id}/regenerate/`: week_index, topic_index, instruction; creates a separate async job/draft.
- `POST ai-drafts/{id}/confirm/`: idempotent import into DRAFT CourseVersion. Does not publish.
- `GET notifications/`, `POST notifications/{id}/read/`.
- `GET dashboard/`, admin `audit/`, admin `ai-usage/`.
- Anonymous `GET public-content/?language=ru|kk`.

Lists use `{count,next,previous,results}` and `?page=N`. Search where supported: `?search=`; ordering: `?ordering=created_at` or `-created_at`. `/api/schema/` exposes OpenAPI; `/api/docs/` renders Swagger when its UI assets are available. `/health/` is liveness; `/ready/` verifies DB and Redis.
