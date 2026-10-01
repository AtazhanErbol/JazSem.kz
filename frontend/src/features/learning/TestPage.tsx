import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { Attempt, Page } from "../../entities/types";
import type { AttemptSummary, TestInfo } from "../../entities/learning";
import { useUser } from "../../app/Auth";
import { api } from "../../services/api";
import { Badge, ErrorState, Loading, Modal } from "../../components/UI";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useAction } from "../../hooks/useAction";
import { queryKeys } from "../../services/queryKeys";
import { Pagination } from "../../components/Pagination";
import { useUnsavedChanges } from "../../hooks/useUnsavedChanges";

export function TestPage() {
  const { id } = useParams();
  const [params] = useSearchParams();
  return <TestScreen key={`${id}:${params.get("attempt") || ""}`} id={id!} />;
}
function TestScreen({ id }: { id: string }) {
  const { t } = useTranslation();
  const action = useAction();
  const [params, setParams] = useSearchParams();
  const attemptId = params.get("attempt") || "";
  const historyPage = Math.max(1, Number(params.get("page")) || 1);
  const user = useUser();
  const draftKey = `jazsem:pending-answers:${user.id}:${attemptId}`;
  const [localAnswers, setLocalAnswers] = useState<Record<string, string[]>>(
    () => {
      try {
        const value: unknown = JSON.parse(
          sessionStorage.getItem(draftKey) || "{}",
        );
        if (value && typeof value === "object" && !Array.isArray(value))
          return Object.fromEntries(
            Object.entries(value).filter(
              ([, options]) =>
                Array.isArray(options) &&
                options.every((option) => typeof option === "string"),
            ),
          );
      } catch {
        /* Storage can be unavailable. Server answers remain authoritative. */
      }
      return {};
    },
  );
  const failedAnswers = Object.keys(localAnswers);
  const storeAnswers = (value: Record<string, string[]>) => {
    setLocalAnswers(value);
    try {
      if (Object.keys(value).length)
        sessionStorage.setItem(draftKey, JSON.stringify(value));
      else sessionStorage.removeItem(draftKey);
    } catch {
      /* In-memory retry remains available. */
    }
  };
  const setAttemptId = (value: string) => {
    setParams(
      (p) => {
        p.set("attempt", value);
        return p;
      },
      { replace: true },
    );
  };
  const [confirm, setConfirm] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [offset, setOffset] = useState(0);
  const info = useQuery({
    queryKey: queryKeys.detail("tests", id!),
    queryFn: ({ signal }) =>
      api<TestInfo>(`tests/${id}/`, "GET", undefined, signal),
  });
  const history = useQuery({
    queryKey: ["attempts", id, historyPage],
    queryFn: ({ signal }) =>
      api<Page<AttemptSummary>>(
        `attempts/?test=${id}&page=${historyPage}`,
        "GET",
        undefined,
        signal,
      ),
  });
  const query = useQuery({
    queryKey: queryKeys.detail("attempts", attemptId),
    queryFn: ({ signal }) =>
      api<Attempt>(`attempts/${attemptId}/`, "GET", undefined, signal),
    enabled: !!attemptId,
    refetchInterval: (q) =>
      q.state.data?.status === "IN_PROGRESS" && !q.state.error ? 10000 : false,
  });
  useEffect(() => {
    if (query.data?.status && query.data.status !== "IN_PROGRESS") return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [query.data?.status]);
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
  useEffect(() => {
    if (query.data?.status && query.data.status !== "IN_PROGRESS") {
      try {
        sessionStorage.removeItem(draftKey);
      } catch {
        /* Storage is optional. */
      }
    }
  }, [query.data?.status, draftKey]);
  useUnsavedChanges(
    failedAnswers.length > 0 &&
      query.data?.status !== "GRADED" &&
      query.data?.status !== "EXPIRED",
  );
  async function save(question: string, values: string[]) {
    const pending = { ...localAnswers, [question]: values };
    storeAnswers(pending);
    const result = await action.run<{ saved: boolean }>(
      `attempts/${attemptId}/answer/`,
      { question, selected_options: values },
      "POST",
      t("ux.answerSaved"),
    );
    if (result.ok) {
      const next = { ...pending };
      delete next[question];
      storeAnswers(next);
    }
  }
  if (info.isPending) return <Loading />;
  if (info.error)
    return <ErrorState error={info.error} retry={() => void info.refetch()} />;
  const active =
    query.data?.status === "IN_PROGRESS" ||
    history.data?.results.some((attempt) => attempt.status === "IN_PROGRESS");
  const blocked =
    !active &&
    (info.data.available_from &&
    Date.parse(info.data.available_from) > now + offset
      ? "ux.notStarted"
      : info.data.available_until &&
          Date.parse(info.data.available_until) <= now + offset
        ? "ux.testClosed"
        : history.data && history.data.count >= info.data.max_attempts
          ? "ux.attemptsExhausted"
          : "");
  const canStart = user.role === "STUDENT" && !blocked && !!history.data;

  return (
    <>
      <Link to="/app/tests">← {t("tests")}</Link>
      <Link
        className="button"
        to={`/app/courses/${info.data.course_id}?activity=${id}`}
      >
        {t("ux.backToCourse")}
      </Link>
      <div className="page-heading">
        <h1>{String(info.data.title)}</h1>
        {query.data?.status === "IN_PROGRESS" && (
          <Badge>
            {t("remaining")}: {Math.floor(remaining / 60)}:
            {String(remaining % 60).padStart(2, "0")}
          </Badge>
        )}
      </div>
      {blocked && (
        <p className="notice" role="status">
          {t(blocked)}
        </p>
      )}
      {action.feedback}
      <p role="status" aria-live="polite">
        {action.pending
          ? t("ux.answerSaving")
          : failedAnswers.length
            ? t("ux.answerUnsaved")
            : ""}
      </p>
      {history.isPending && <Loading />}
      {history.error && (
        <ErrorState
          error={history.error}
          retry={() => void history.refetch()}
        />
      )}
      {history.data && history.data.count > 0 && (
        <section className="panel">
          <h2>{t("attemptHistory")}</h2>
          <div className="row-actions">
            {history.data.results.map((attempt) => (
              <button key={attempt.id} onClick={() => setAttemptId(attempt.id)}>
                {t("attempt_number")} {String(attempt.attempt_number)} ·{" "}
                {t(String(attempt.status))}
                {attempt.score != null ? ` · ${attempt.score}/100` : ""}
              </button>
            ))}
            {query.data &&
              query.data.status !== "IN_PROGRESS" &&
              history.data.count < Number(info.data.max_attempts) &&
              canStart && (
                <button
                  disabled={action.pending}
                  onClick={async () => {
                    const result = await action.run<AttemptSummary>(
                      `tests/${id}/start/`,
                    );
                    if (result.ok) setAttemptId(result.data.id);
                  }}
                >
                  {t("retryTest")}
                </button>
              )}
          </div>
        </section>
      )}
      {history.data && (
        <Pagination
          page={historyPage}
          count={history.data.count}
          onChange={(value) =>
            setParams((p) => {
              p.set("page", String(value));
              return p;
            })
          }
        />
      )}
      {!attemptId ? (
        <section className="panel">
          <p>{String(info.data.description)}</p>
          <p>
            {t("time_limit_minutes")}: {String(info.data.time_limit_minutes)} ·{" "}
            {t("max_attempts")}: {String(info.data.max_attempts)}
          </p>
          <button
            className="primary"
            disabled={action.pending || !canStart}
            onClick={async () => {
              const attempt = await action.run<AttemptSummary>(
                `tests/${id}/start/`,
              );
              if (attempt.ok) setAttemptId(attempt.data.id);
            }}
          >
            {t("start")} / {t("continue")}
          </button>
        </section>
      ) : query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
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
                        (query.data.status === "IN_PROGRESS"
                          ? localAnswers[question.id]
                          : undefined) ?? query.data.answers[question.id]
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
                      storeAnswers({ ...localAnswers, [question.id]: values });
                      await save(question.id, values);
                    }}
                  />
                  {option.text}
                </label>
              ))}
              {failedAnswers.includes(question.id) &&
                query.data.status === "IN_PROGRESS" && (
                  <button
                    disabled={action.pending}
                    onClick={() =>
                      void save(question.id, localAnswers[question.id])
                    }
                  >
                    {t("ux.retryAnswer")}
                  </button>
                )}
            </fieldset>
          ))}
          {query.data.status === "IN_PROGRESS" && (
            <button
              className="primary"
              disabled={action.pending || failedAnswers.length > 0}
              onClick={() => setConfirm(true)}
            >
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
              const result = await action.run(`attempts/${attemptId}/finish/`);
              if (result.ok) setConfirm(false);
            }}
          >
            {t("confirm")}
          </button>
        </Modal>
      )}
    </>
  );
}
