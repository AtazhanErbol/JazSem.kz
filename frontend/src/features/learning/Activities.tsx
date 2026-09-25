import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { Attempt, Page, Progress, Row } from "../../entities/types";
import { api, allRows } from "../../services/api";
import {
  Badge,
  Empty,
  ErrorState,
  Loading,
  Modal,
  ProgressBar,
} from "../../components/UI";
import { useAction } from "../../hooks/useAction";

export function AssignmentPage() {
  const { id } = useParams();
  const { t } = useTranslation();
  const action = useAction();
  const [text, setText] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const assignment = useQuery({
    queryKey: ["assignment", id],
    queryFn: () => api<Row>(`assignments/${id}/`),
  });
  const history = useQuery({
    queryKey: ["submissions", id],
    queryFn: () => api<Page<Row>>(`submissions/?assignment=${id}`),
  });
  if (assignment.isPending) return <Loading />;
  if (assignment.error) return <ErrorState error={assignment.error} />;
  return (
    <>
      <Link to="/app/assignments">← {t("assignments")}</Link>
      <h1>{String(assignment.data.title)}</h1>
      <section className="panel">
        <p className="prose">{String(assignment.data.instructions)}</p>
        {assignment.data.deadline != null && (
          <p>
            {t("deadline")}:{" "}
            {new Date(String(assignment.data.deadline)).toLocaleString()}
          </p>
        )}
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const body = new FormData();
            body.append("text_answer", text);
            Array.from(files || []).forEach((file) =>
              body.append("files", file),
            );
            await action.run(`assignments/${id}/submit/`, body);
          }}
        >
          <label>
            {t("answer")}
            <textarea
              rows={9}
              value={text}
              onChange={(e) => setText(e.target.value)}
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
        </form>
      </section>
      <h2>{t("submissions")}</h2>
      {history.data?.results.map((row) => (
        <article className="panel" key={row.id}>
          <Badge>{String(row.status)}</Badge>
          <p className="prose">{String(row.text_answer)}</p>
          <p>{String(row.teacher_comment || "")}</p>
          {row.score != null && <strong>{String(row.score)} / 100</strong>}
        </article>
      ))}
    </>
  );
}

export function TestPage() {
  const { id } = useParams();
  const { t } = useTranslation();
  const action = useAction();
  const [attemptId, setAttemptId] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [offset, setOffset] = useState(0);
  const [localAnswers, setLocalAnswers] = useState<Record<string, string[]>>(
    {},
  );
  const info = useQuery({
    queryKey: ["test", id],
    queryFn: () => api<Row>(`tests/${id}/`),
  });
  const query = useQuery({
    queryKey: ["attempt", attemptId],
    queryFn: () => api<Attempt>(`attempts/${attemptId}/`),
    enabled: !!attemptId,
    refetchInterval: 10000,
  });
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (query.data?.server_time)
      setOffset(new Date(query.data.server_time).getTime() - Date.now());
  }, [query.data?.server_time]);
  const remaining = query.data
    ? Math.max(
        0,
        Math.ceil(
          (new Date(query.data.expires_at).getTime() - now - offset) / 1000,
        ),
      )
    : 0;
  useEffect(() => {
    if (query.data?.status === "IN_PROGRESS" && remaining === 0)
      void query.refetch();
  }, [remaining, query.data?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  if (info.isPending) return <Loading />;
  if (info.error) return <ErrorState error={info.error} />;
  return (
    <>
      <Link to="/app/tests">← {t("tests")}</Link>
      <div className="page-heading">
        <h1>{String(info.data.title)}</h1>
        {query.data && (
          <Badge>
            {t("remaining")}: {Math.floor(remaining / 60)}:
            {String(remaining % 60).padStart(2, "0")}
          </Badge>
        )}
      </div>
      {action.feedback}
      {!attemptId ? (
        <section className="panel">
          <p>{String(info.data.description)}</p>
          <p>
            {t("time_limit_minutes")}: {String(info.data.time_limit_minutes)} ·{" "}
            {t("max_attempts")}: {String(info.data.max_attempts)}
          </p>
          <button
            className="primary"
            disabled={action.pending}
            onClick={async () => {
              const attempt = await action.run<Row>(`tests/${id}/start/`);
              if (attempt) setAttemptId(attempt.id);
            }}
          >
            {t("start")} / {t("continue")}
          </button>
        </section>
      ) : query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} />
      ) : (
        <>
          {query.data.status !== "IN_PROGRESS" && (
            <section className="result-card">
              <h2>{t("result")}</h2>
              <strong>{query.data.score} / 100</strong>
              <Badge>{query.data.status}</Badge>
            </section>
          )}
          {query.data.questions.map((question, index) => (
            <fieldset className="panel" key={question.id}>
              <legend>
                {index + 1}. {question.text}
              </legend>
              {question.options.map((option) => (
                <label className="answer-option" key={option.id}>
                  <input
                    type={
                      question.type === "SINGLE_CHOICE" ? "radio" : "checkbox"
                    }
                    name={question.id}
                    checked={
                      (
                        localAnswers[question.id] ??
                        query.data.answers[question.id]
                      )?.includes(option.id) || false
                    }
                    disabled={
                      query.data.status !== "IN_PROGRESS" ||
                      remaining === 0 ||
                      action.pending
                    }
                    onChange={async (e) => {
                      const previous =
                        localAnswers[question.id] ??
                        query.data.answers[question.id] ??
                        [];
                      const values =
                        question.type === "SINGLE_CHOICE"
                          ? [option.id]
                          : e.target.checked
                            ? [...previous, option.id]
                            : previous.filter((x) => x !== option.id);
                      setLocalAnswers((old) => ({
                        ...old,
                        [question.id]: values,
                      }));
                      const result = await action.run<{ saved: boolean }>(
                        `attempts/${attemptId}/answer/`,
                        { question: question.id, selected_options: values },
                      );
                      if (!result)
                        setLocalAnswers((old) => ({
                          ...old,
                          [question.id]: previous,
                        }));
                    }}
                  />
                  {option.text}
                </label>
              ))}
            </fieldset>
          ))}
          {query.data.status === "IN_PROGRESS" && (
            <button className="primary" onClick={() => setConfirm(true)}>
              {t("finish")}
            </button>
          )}
        </>
      )}
      {confirm && (
        <Modal title={t("finish")} onClose={() => setConfirm(false)}>
          <p>{t("confirmText")}</p>
          <button
            className="primary"
            disabled={action.pending}
            onClick={async () => {
              await action.run(`attempts/${attemptId}/finish/`);
              setConfirm(false);
            }}
          >
            {t("confirm")}
          </button>
        </Modal>
      )}
    </>
  );
}

export function GradePage() {
  const { id } = useParams();
  const { t } = useTranslation();
  const action = useAction();
  const [score, setScore] = useState("");
  const [comment, setComment] = useState("");
  const query = useQuery({
    queryKey: ["submission", id],
    queryFn: () => api<Row>(`submissions/${id}/`),
  });
  const files = useQuery({
    queryKey: ["submission-files", id],
    queryFn: () => api<Row[]>(`submissions/${id}/files/`),
  });
  if (query.isPending) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  return (
    <>
      <h1>{t("submissions")}</h1>
      <section className="panel">
        <Badge>{String(query.data.status)}</Badge>
        <h2>{t("studentWork")}</h2>
        <p className="prose">{String(query.data.text_answer)}</p>
        {files.data?.map((file) => (
          <a
            className="button"
            key={file.id}
            href={`/api/v1/submission-files/${file.id}/download/`}
          >
            {String(file.original_filename)}
          </a>
        ))}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(`submissions/${id}/grade/`, {
              score: Number(score),
              comment,
            });
          }}
        >
          <label>
            {t("score")}
            <input
              type="number"
              min="0"
              value={score}
              onChange={(e) => setScore(e.target.value)}
              required
            />
          </label>
          <label>
            {t("comment")}
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={5}
            />
          </label>
          <div className="row-actions">
            <button className="primary" disabled={action.pending}>
              {t("grade")}
            </button>
            <button
              type="button"
              disabled={action.pending || !comment.trim()}
              onClick={() =>
                void action.run(`submissions/${id}/request-revision/`, {
                  comment,
                })
              }
            >
              {t("revision")}
            </button>
          </div>
          {action.feedback}
        </form>
      </section>
    </>
  );
}

export function ResultsPage({ mode }: { mode: "grades" | "progress" }) {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: ["enrollments", "results"],
    queryFn: () => api<Page<Row>>("enrollments/"),
  });
  return (
    <>
      <h1>{t(mode)}</h1>
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} />
      ) : query.data.results.length ? (
        query.data.results.map((row) => (
          <ResultRow key={row.id} row={row} mode={mode} />
        ))
      ) : (
        <Empty />
      )}
    </>
  );
}
function ResultRow({ row, mode }: { row: Row; mode: "grades" | "progress" }) {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: [mode, row.id],
    queryFn: () =>
      api<
        Progress & {
          score: number;
          components: { kind: string; weight: number; score: number }[];
        }
      >(`enrollments/${row.id}/${mode}/`),
  });
  const course = useQuery({
    queryKey: ["course", row.course],
    queryFn: () => api<Row>(`courses/${String(row.course)}/`),
  });
  return (
    <section className="panel">
      <h2>{String(course.data?.title || "…")}</h2>
      <small>{String(row.student)}</small>
      {query.data &&
        (mode === "progress" ? (
          <>
            <h3>{query.data.percent}%</h3>
            <ProgressBar value={query.data.percent} />
            <small>
              {query.data.completed} / {query.data.total}
            </small>
          </>
        ) : (
          <>
            <h3>{query.data.score} / 100</h3>
            {query.data.components.map((c) => (
              <p key={c.kind}>
                {t(c.kind)} ({c.weight}%) — {c.score}
              </p>
            ))}
          </>
        ))}
      {query.error && <ErrorState error={query.error} />}
    </section>
  );
}

export function GroupPage() {
  const { id } = useParams();
  const { t } = useTranslation();
  const action = useAction();
  const [student, setStudent] = useState("");
  const members = useQuery({
    queryKey: ["members", id],
    queryFn: () => api<Row[]>(`groups/${id}/members/`),
  });
  const students = useQuery({
    queryKey: ["options", "students"],
    queryFn: () => allRows("users/?role=STUDENT"),
  });
  return (
    <>
      <h1>{t("members")}</h1>
      <section className="panel">
        <label>
          {t("student")}
          <select value={student} onChange={(e) => setStudent(e.target.value)}>
            <option value="">—</option>
            {students.data?.map((s) => (
              <option key={s.id} value={s.id}>
                {String(s.first_name)} {String(s.last_name)} · {String(s.email)}
              </option>
            ))}
          </select>
        </label>
        <button
          className="primary"
          disabled={!student || action.pending}
          onClick={() => void action.run(`groups/${id}/members/`, { student })}
        >
          {t("addMember")}
        </button>
        {action.feedback}
      </section>
      {members.data?.map((m) => (
        <div className="record-row" key={m.id}>
          <span>
            {String(
              students.data?.find((s) => s.id === m.student)?.email ||
                m.student,
            )}
          </span>
          <button
            disabled={action.pending}
            onClick={() =>
              void action.run(`groups/${id}/remove-member/`, {
                student: m.student,
              })
            }
          >
            {t("removeMember")}
          </button>
        </div>
      ))}
    </>
  );
}
