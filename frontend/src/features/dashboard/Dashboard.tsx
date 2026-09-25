import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ArrowUpRight, BookOpen, Sparkles } from "lucide-react";
import { useUser } from "../../app/Auth";
import { api } from "../../services/api";
import type { Page, Row } from "../../entities/types";
import { Empty, ErrorState, Loading } from "../../components/UI";

export function Dashboard() {
  const user = useUser();
  const { t } = useTranslation();
  const stats = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Record<string, number>>("dashboard/"),
  });
  const courses = useQuery({
    queryKey: ["courses", "dashboard"],
    queryFn: () => api<Page<Row>>("courses/"),
  });
  const assignments = useQuery({
    queryKey: ["assignments", "dashboard"],
    queryFn: () => api<Page<Row>>("assignments/?ordering=deadline"),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            {new Date().toLocaleDateString(undefined, {
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
          </span>
          <h1>
            {t("greeting")}, {user.first_name || user.email.split("@")[0]}{" "}
            <span className="greeting-dot">.</span>
          </h1>
          <p className="muted">{t("welcome")}</p>
        </div>
        {user.role !== "STUDENT" && (
          <Link className="button primary" to="/app/courses">
            + {t("createCourse")}
          </Link>
        )}
      </div>
      <section className="welcome-banner">
        <div>
          <span className="eyebrow">JAZSEM / {t("continue")}</span>
          <h2>
            {t(user.role === "STUDENT" ? "studentTitle" : "teacherTitle")}
          </h2>
          <p>{t(user.role === "STUDENT" ? "studentText" : "teacherText")}</p>
          <Link
            className="button light"
            to={user.role === "STUDENT" ? "/app/courses" : "/app/ai"}
          >
            {user.role !== "STUDENT" && <Sparkles size={18} />}{" "}
            {t(user.role === "STUDENT" ? "continue" : "ai")}{" "}
            <ArrowUpRight size={18} />
          </Link>
        </div>
        <div className="banner-glyph" aria-hidden="true">
          J<span>↗</span>
        </div>
      </section>
      {stats.isPending ? (
        <Loading />
      ) : stats.error ? (
        <ErrorState error={stats.error} />
      ) : (
        <div className="stats-grid">
          {(user.role === "STUDENT"
            ? ["courses", "enrollments"]
            : ["courses", "students", "groups", "review"]
          ).map((key) => (
            <div className="stat" key={key}>
              <span>{t(key)}</span>
              <strong>{stats.data[key]}</strong>
              <span className="stat-line" />
            </div>
          ))}
        </div>
      )}
      <div className="dashboard-columns">
        <section>
          <div className="section-heading">
            <h2>{t("courses")}</h2>
            <Link to="/app/courses">{t("all")} ↗</Link>
          </div>
          {courses.isPending ? (
            <Loading />
          ) : courses.error ? (
            <ErrorState error={courses.error} />
          ) : courses.data.results.length ? (
            courses.data.results.slice(0, 4).map((course) => (
              <Link
                className="learning-row"
                key={course.id}
                to={"/app/courses/" + course.id}
              >
                <span className="course-icon">
                  <BookOpen />
                </span>
                <div>
                  <h3>{String(course.title)}</h3>
                  <small>{t(String(course.status))}</small>
                </div>
                <ArrowUpRight />
              </Link>
            ))
          ) : (
            <Empty>
              <p>
                {t(user.role === "STUDENT" ? "studentHint" : "teacherHint")}
              </p>
            </Empty>
          )}
        </section>
        <section>
          <div className="section-heading">
            <h2>{t("assignments")}</h2>
            <Link to="/app/assignments">{t("all")} ↗</Link>
          </div>
          {assignments.data?.results.length ? (
            assignments.data.results.slice(0, 5).map((a) => (
              <Link
                className="deadline-row"
                key={a.id}
                to={
                  user.role === "STUDENT"
                    ? "/app/assignments/" + a.id
                    : "/app/assignments"
                }
              >
                <span className="deadline-dot" />
                <div>
                  <h3>{String(a.title)}</h3>
                  <small>
                    {a.deadline
                      ? new Date(String(a.deadline)).toLocaleString()
                      : "—"}
                  </small>
                </div>
              </Link>
            ))
          ) : (
            <Empty />
          )}
        </section>
      </div>
    </>
  );
}
