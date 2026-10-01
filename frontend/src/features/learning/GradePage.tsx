import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { SubmissionDetails, PrivateFile } from "../../entities/learning";
import { api, ApiError } from "../../services/api";
import { Badge, ErrorState, Loading } from "../../components/UI";
import { Link, useParams } from "react-router-dom";
import { useAction } from "../../hooks/useAction";
import { useUnsavedChanges } from "../../hooks/useUnsavedChanges";
import { queryKeys } from "../../services/queryKeys";
import { useUser } from "../../app/Auth";

export function GradePage() {
  const { id } = useParams();
  return <GradeDetails key={id} id={id!} />;
}
function GradeDetails({ id }: { id: string }) {
  const { t, i18n } = useTranslation();
  const user = useUser();
  const query = useQuery({
    queryKey: queryKeys.detail("submissions", id),
    queryFn: ({ signal }) =>
      api<SubmissionDetails>(`submissions/${id}/`, "GET", undefined, signal),
  });
  const files = useQuery({
    queryKey: ["submission-files", id],
    queryFn: ({ signal }) =>
      api<PrivateFile[]>(`submissions/${id}/files/`, "GET", undefined, signal),
  });
  if (query.isPending) return <Loading />;
  if (query.error)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  const row = query.data;
  return (
    <>
      <Link to="/app/submissions">← {t("submissions")}</Link>
      <h1>{row.assignment_title}</h1>
      <section className="panel">
        <Badge>{row.status}</Badge>
        <h2>{t("studentWork")}</h2>
        <p>
          {row.student_name} ·{" "}
          {new Date(row.submitted_at).toLocaleString(i18n.language)}
        </p>
        <p className="prose">{row.text_answer || "—"}</p>
        {files.isPending && <Loading />}
        {files.error && (
          <ErrorState error={files.error} retry={() => void files.refetch()} />
        )}
        <div className="row-actions">
          {files.data?.map((file) => (
            <a
              className="button"
              key={file.id}
              href={`/api/v1/submission-files/${file.id}/download/`}
            >
              {file.original_filename}
            </a>
          ))}
        </div>
        {row.status === "REVISION_REQUESTED" ? (
          <div className="notice">
            <p>{t("ux.waitingRevision")}</p>
            <p>{row.teacher_comment}</p>
          </div>
        ) : (
          user.role !== "STUDENT" && <ReviewForm row={row} />
        )}
      </section>
    </>
  );
}
function ReviewForm({ row }: { row: SubmissionDetails }) {
  const { t } = useTranslation();
  const action = useAction();
  const [score, setScore] = useState(
    row.score == null
      ? ""
      : String(Number(((Number(row.score) * row.max_score) / 100).toFixed(2))),
  );
  const [comment, setComment] = useState(row.teacher_comment);
  const [dirty, setDirty] = useState(false);
  useUnsavedChanges(dirty);
  const errors =
    action.error instanceof ApiError ? action.error.fieldErrors : {};
  async function send(kind: "grade" | "request-revision") {
    const result = await action.run(
      `submissions/${row.id}/${kind}/`,
      kind === "grade" ? { score: Number(score), comment } : { comment },
    );
    if (result.ok) setDirty(false);
  }
  return (
    <form
      data-dirty={dirty}
      onSubmit={(event) => {
        event.preventDefault();
        void send("grade");
      }}
    >
      <label>
        {t("score")} (0–{row.max_score})
        <input
          type="number"
          aria-label={t("score")}
          min="0"
          max={row.max_score}
          step="0.01"
          value={score}
          onChange={(event) => {
            setScore(event.target.value);
            setDirty(true);
          }}
          required
          aria-invalid={!!errors.score}
          aria-describedby={errors.score ? "score-error" : undefined}
        />
        {errors.score && (
          <span id="score-error" className="field-error" role="alert">
            {errors.score}
          </span>
        )}
      </label>
      <label>
        {t("comment")}
        <textarea
          value={comment}
          maxLength={10000}
          onChange={(event) => {
            setComment(event.target.value);
            setDirty(true);
          }}
          rows={5}
          aria-invalid={!!errors.comment}
          aria-describedby={errors.comment ? "comment-error" : undefined}
        />
        {errors.comment && (
          <span id="comment-error" className="field-error" role="alert">
            {errors.comment}
          </span>
        )}
      </label>
      <div className="row-actions">
        <button className="primary" disabled={action.pending}>
          {t("grade")}
        </button>
        <button
          type="button"
          disabled={action.pending || !comment.trim()}
          onClick={() => void send("request-revision")}
        >
          {t("revision")}
        </button>
      </div>
      {action.feedback}
    </form>
  );
}
