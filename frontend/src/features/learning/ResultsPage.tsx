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
          <section className="panel" key={row.id}>
            <h2>
              <Link to={`/app/courses/${row.course}`}>{row.course_title}</Link>
            </h2>
            <small>{row.student_name}</small>
            {mode === "progress" ? (
              <>
                <h3>{row.progress.percent}%</h3>
                <ProgressBar value={row.progress.percent} />
                <small>
                  {row.progress.completed} / {row.progress.total}
                </small>
              </>
            ) : (
              <>
                <h3>{row.grades.score} / 100</h3>
                {row.grades.components.map((component) => (
                  <p key={component.kind}>
                    {t(component.kind)} ({component.weight}%) —{" "}
                    {component.score}
                  </p>
                ))}
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
