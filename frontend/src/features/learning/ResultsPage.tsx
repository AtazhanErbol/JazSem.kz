import { useQuery } from "@tanstack/react-query";
import { useSearchParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { Page } from "../../entities/types";
import type { EnrollmentSummary } from "../../entities/learning";
import { api } from "../../services/api";
import { queryKeys } from "../../services/queryKeys";
import { Empty, ErrorState, Loading, ProgressBar } from "../../components/UI";
import { ResourceFilters } from "../manage/ResourceFilters";
import { Pagination } from "../../components/Pagination";

export function ResultsPage({ mode }: { mode: "grades" | "progress" }) {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const query = useQuery({
    queryKey: queryKeys.list("enrollments", `summaries:${params}`),
    queryFn: ({ signal }) =>
      api<Page<EnrollmentSummary>>(
        `enrollments/summaries/?${params}`,
        "GET",
        undefined,
        signal,
      ),
  });
  return (
    <>
      <h1>{t(mode)}</h1>
      <ResourceFilters
        resource="enrollments"
        params={params}
        change={(key, value) =>
          setParams((p) => {
            if (value) p.set(key, value);
            else p.delete(key);
            p.delete("page");
            return p;
          })
        }
      />
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : query.data.results.length ? (
        query.data.results.map((row) => (
          <section className="panel learning-result-card" key={row.id}>
            <h2>
              <Link to={`/app/courses/${row.course}`}>{row.course_title}</Link>
            </h2>
            <p className="result-student">
              {t("learningDisplay.student", { name: row.student_name })}
            </p>
            {mode === "progress" ? (
              <>
                <div className="result-summary">
                  <span>{t("learningDisplay.progressTitle")}</span>
                  <strong>{row.progress.percent}%</strong>
                </div>
                <ProgressBar value={row.progress.percent} />
                <p>
                  {row.progress.total
                    ? t("learningDisplay.completed", {
                        done: row.progress.completed,
                        total: row.progress.total,
                      })
                    : t("learningDisplay.noElements")}
                </p>
                <p className="field-hint">
                  {t("learningDisplay.progressHint")}
                </p>
              </>
            ) : (
              <>
                <div className="result-summary">
                  <span>{t("learningDisplay.currentScore")}</span>
                  <strong>
                    {row.grades.score} <small>/ 100</small>
                  </strong>
                </div>
                <div className="result-components">
                  {row.grades.components.map((component) => (
                    <div className="result-component" key={component.kind}>
                      <h3>{t(component.kind)}</h3>
                      <dl>
                        <div>
                          <dt>{t("learningDisplay.average")}</dt>
                          <dd>{component.score} / 100</dd>
                        </div>
                        <div>
                          <dt>{t("learningDisplay.weight")}</dt>
                          <dd>{component.weight}%</dd>
                        </div>
                        <div>
                          <dt>{t("learningDisplay.contribution")}</dt>
                          <dd>
                            {Number(
                              (
                                (component.score * component.weight) /
                                100
                              ).toFixed(2),
                            )}{" "}
                            / {component.weight}
                          </dd>
                        </div>
                      </dl>
                    </div>
                  ))}
                </div>
                <p className="field-hint">
                  {t(
                    row.grades.components.length
                      ? "learningDisplay.gradeHint"
                      : "learningDisplay.noGrading",
                  )}
                </p>
              </>
            )}
          </section>
        ))
      ) : (
        <Empty />
      )}
      {query.data && (
        <Pagination
          count={query.data.count}
          page={page}
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
