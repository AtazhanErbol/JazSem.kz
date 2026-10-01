import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { Page } from "../../entities/types";
import type {
  AssignmentDetails,
  SubmissionDetails,
} from "../../entities/learning";
import { api } from "../../services/api";
import { Badge, ErrorState, Loading } from "../../components/UI";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useAction } from "../../hooks/useAction";
import { useUser } from "../../app/Auth";
import { useUnsavedChanges } from "../../hooks/useUnsavedChanges";
import { Pagination } from "../../components/Pagination";
import { queryKeys } from "../../services/queryKeys";

export function AssignmentPage() {
  const { id } = useParams();
  return <AssignmentScreen key={id} id={id!} />;
}
function AssignmentScreen({ id }: { id: string }) {
  const { t, i18n } = useTranslation();
  const user = useUser();
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const draftKey = `jazsem:submission:${user.id}:${id}`;
  const action = useAction();
  const [text, setText] = useState(() => {
    try {
      return sessionStorage.getItem(draftKey) || "";
    } catch {
      return "";
    }
  });
  const saveDraft = (value: string) => {
    try {
      if (value) sessionStorage.setItem(draftKey, value);
      else sessionStorage.removeItem(draftKey);
    } catch {
      /* The form and navigation guard still preserve the in-memory draft. */
    }
  };
  const [files, setFiles] = useState<FileList | null>(null);
  const assignment = useQuery({
    queryKey: queryKeys.detail("assignments", id!),
    queryFn: ({ signal }) =>
      api<AssignmentDetails>(`assignments/${id}/`, "GET", undefined, signal),
  });
  const newest = useQuery({
    queryKey: ["submissions", id],
    queryFn: ({ signal }) =>
      api<Page<SubmissionDetails>>(
        `submissions/?assignment=${id}`,
        "GET",
        undefined,
        signal,
      ),
  });
  const older = useQuery({
    queryKey: ["submissions", id, page],
    queryFn: ({ signal }) =>
      api<Page<SubmissionDetails>>(
        `submissions/?assignment=${id}&page=${page}`,
        "GET",
        undefined,
        signal,
      ),
    enabled: page > 1,
  });
  const history = page === 1 ? newest : older;
  const latest = newest.data?.results[0];
  const submitted = latest && latest.status !== "REVISION_REQUESTED";
  useUnsavedChanges(!submitted && (!!text || !!files?.length));
  if (assignment.isPending) return <Loading />;
  if (assignment.error) return <ErrorState error={assignment.error} />;
  return (
    <>
      <Link to="/app/assignments">← {t("assignments")}</Link>
      {assignment.data.course_id && (
        <Link
          className="button"
          to={`/app/courses/${assignment.data.course_id}?activity=${id}`}
        >
          {t("ux.backToCourse")}
        </Link>
      )}
      <h1>{String(assignment.data.title)}</h1>
      <section className="panel">
        <p className="prose">{String(assignment.data.instructions)}</p>
        {assignment.data.deadline != null && (
          <p>
            {t("deadline")}:{" "}
            {new Date(assignment.data.deadline).toLocaleString(i18n.language)}
          </p>
        )}
        {newest.error && (
          <ErrorState
            error={newest.error}
            retry={() => void newest.refetch()}
          />
        )}
        {latest?.status === "REVISION_REQUESTED" && (
          <p className="notice">
            {t("REVISION_REQUESTED")}: {latest.teacher_comment}
          </p>
        )}
        {submitted && <p className="notice">{t("submissionLocked")}</p>}
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const body = new FormData();
            body.append("text_answer", text);
            Array.from(files || []).forEach((file) =>
              body.append("files", file),
            );
            const result = await action.run(`assignments/${id}/submit/`, body);
            if (result.ok) {
              saveDraft("");
              setText("");
              setFiles(null);
            }
          }}
        >
          <fieldset
            disabled={
              action.pending ||
              newest.isPending ||
              !!newest.error ||
              user.role !== "STUDENT" ||
              !!submitted
            }
          >
            <label>
              {t("answer")}
              <textarea
                rows={9}
                value={text}
                onChange={(e) => {
                  setText(e.target.value);
                  saveDraft(e.target.value);
                }}
              />
            </label>
            <label>
              {t("files")}
              <input
                type="file"
                multiple
                accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg"
                onChange={(e) => setFiles(e.target.files)}
              />
            </label>
            <button className="primary" disabled={action.pending}>
              {t("submit")}
            </button>
            {action.feedback}
          </fieldset>
        </form>
      </section>
      <h2>{t("submissions")}</h2>
      {history.isPending && <Loading />}
      {history.error && (
        <ErrorState
          error={history.error}
          retry={() => void history.refetch()}
        />
      )}
      {history.data?.results.map((row) => (
        <article className="panel" key={row.id}>
          <Badge>{String(row.status)}</Badge>
          <p className="prose">{String(row.text_answer)}</p>
          <p>{String(row.teacher_comment || "")}</p>
          {row.score != null && <strong>{String(row.score)} / 100</strong>}
        </article>
      ))}
      {history.data && (
        <Pagination
          page={page}
          count={history.data.count}
          onChange={(value) =>
            setParams((p) => {
              p.set("page", String(value));
              return p;
            })
          }
        />
      )}
    </>
  );
}
