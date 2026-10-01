import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Check } from "lucide-react";
import { useUser } from "../../app/Auth";
import { useAction } from "../../hooks/useAction";
import { api } from "../../services/api";
import { queryKeys } from "../../services/queryKeys";
import type { Activity, Page, Tree } from "../../entities/types";
import type { EnrollmentSummary } from "../../entities/learning";
import { Empty, ErrorState, Loading, ProgressBar } from "../../components/UI";

export function CoursePlayer() {
  const { id = "" } = useParams();
  const user = useUser();
  const { t } = useTranslation();
  const action = useAction();
  const [params, setParams] = useSearchParams();
  const [outline, setOutline] = useState(
    () => window.matchMedia("(min-width: 900px)").matches,
  );
  const tree = useQuery({
    queryKey: queryKeys.tree(id),
    queryFn: ({ signal }) =>
      api<Tree>(`courses/${id}/tree/`, "GET", undefined, signal),
  });
  const learning = useQuery({
    queryKey: queryKeys.list("enrollments", `player:${id}`),
    queryFn: ({ signal }) =>
      api<Page<EnrollmentSummary>>(
        `enrollments/summaries/?course=${id}`,
        "GET",
        undefined,
        signal,
      ),
  });
  if (tree.isPending || learning.isPending) return <Loading />;
  if (tree.error || learning.error)
    return (
      <ErrorState
        error={tree.error || learning.error}
        retry={() => {
          void tree.refetch();
          void learning.refetch();
        }}
      />
    );
  const data = tree.data,
    enrollment = learning.data.results[0];
  if (!enrollment) return <Empty />;
  const progress = enrollment.progress;
  const positionKey = `jazsem:position:${user.id}:${id}:${data.version.id}`;
  let savedPosition: string | null = null;
  try {
    savedPosition = localStorage.getItem(positionKey);
  } catch {
    /* URL remains usable. */
  }
  const savePosition = (value: string) => {
    try {
      localStorage.setItem(positionKey, value);
    } catch {
      /* Storage is optional. */
    }
  };
  const entries: { type: string; item: Activity }[] = data.weeks.flatMap(
    (week) =>
      week.topics.flatMap((topic) => [
        ...(topic.content.trim() ? [{ type: "topic", item: topic }] : []),
        ...(["materials", "assignments", "tests"] as const).flatMap((type) =>
          topic[type].map((item) => ({ type, item })),
        ),
      ]),
  );
  const completed = (entry: (typeof entries)[number]) =>
    (entry.type === "topic"
      ? progress.read_topics
      : entry.type === "materials"
        ? progress.materials
        : entry.type === "assignments"
          ? progress.assignments
          : progress.tests
    ).includes(entry.item.id);
  const selected =
    entries.find(
      (entry) => entry.item.id === (params.get("activity") || savedPosition),
    ) ||
    entries.find((entry) => !completed(entry)) ||
    entries[0];
  const select = (entry: (typeof entries)[number]) => {
    savePosition(entry.item.id);
    setParams(
      (p) => {
        p.set("activity", entry.item.id);
        return p;
      },
      { replace: true },
    );
    if (!window.matchMedia("(min-width: 900px)").matches) setOutline(false);
  };
  const next = selected && entries[entries.indexOf(selected) + 1];
  return (
    <>
      <Link to="/app/courses">← {t("courses")}</Link>
      <h1>{String(data.course.title)}</h1>
      <div className="course-progress">
        <span>
          {t("progress")} {progress.percent}%
        </span>
        <ProgressBar value={progress.percent} />
      </div>
      <p className="muted">{t("ux.positionSaved")}</p>
      {progress.percent === 100 && (
        <p className="notice" role="status">
          {t("ux.courseFinished")}
        </p>
      )}
      <button
        className="outline-toggle"
        aria-expanded={outline}
        aria-controls="student-outline"
        onClick={() => setOutline(!outline)}
      >
        {t(outline ? "ux.hideOutline" : "ux.showOutline")}
      </button>
      <div
        className={`course-layout student-player ${outline ? "outline-visible" : "outline-hidden"}`}
      >
        <aside
          className="course-outline"
          id="student-outline"
          hidden={!outline}
        >
          <h2>{t("outline")}</h2>
          {data.weeks.map((week) => (
            <section key={week.id}>
              <h3>
                {week.number}. {week.title}
              </h3>
              {week.topics.map((topic) => (
                <section className="outline-topic" key={topic.id}>
                  <strong>{topic.title}</strong>
                  {entries
                    .filter(
                      (entry) =>
                        entry.item.id === topic.id ||
                        [
                          ...topic.materials,
                          ...topic.assignments,
                          ...topic.tests,
                        ].some((item) => item.id === entry.item.id),
                    )
                    .map((entry) => (
                      <button
                        className={
                          selected === entry
                            ? "outline-item active"
                            : "outline-item"
                        }
                        aria-current={selected === entry ? "step" : undefined}
                        key={entry.item.id}
                        onClick={() => select(entry)}
                      >
                        {completed(entry) && <Check size={14} />}
                        {entry.item.title}
                      </button>
                    ))}
                </section>
              ))}
            </section>
          ))}
        </aside>
        <section className="content-pane" aria-live="polite">
          {!selected ? (
            <Empty />
          ) : (
            <>
              <span className="eyebrow">{t(selected.type)}</span>
              <h2>{selected.item.title}</h2>
              <div className="prose">
                {selected.item.content ||
                  selected.item.instructions ||
                  String(selected.item.description || "")}
              </div>
              <div className="row-actions">
                {selected.item.file && (
                  <a
                    className="button"
                    href={`/api/v1/materials/${selected.item.id}/download/`}
                  >
                    {t("download")}
                  </a>
                )}
                {selected.item.external_url && (
                  <a
                    className="button"
                    href={selected.item.external_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {t("details")} ↗
                  </a>
                )}
                {["topic", "materials"].includes(selected.type) ? (
                  <button
                    className="primary"
                    disabled={action.pending || completed(selected)}
                    onClick={async () => {
                      const result = await action.run(
                        `${selected.type === "topic" ? "topics" : "materials"}/${selected.item.id}/complete/`,
                      );
                      if (result.ok) savePosition((next || selected).item.id);
                    }}
                  >
                    {t(completed(selected) ? "completed" : "complete")}
                  </button>
                ) : (
                  <Link
                    className="button primary"
                    to={`/app/${selected.type}/${selected.item.id}?course=${id}`}
                  >
                    {t(selected.type === "tests" ? "start" : "submit")}
                  </Link>
                )}
              </div>
              {action.feedback}
              {next && (
                <button disabled={action.pending} onClick={() => select(next)}>
                  {t("ux.nextActivity")} → {next.item.title}
                </button>
              )}
            </>
          )}
        </section>
      </div>
    </>
  );
}
