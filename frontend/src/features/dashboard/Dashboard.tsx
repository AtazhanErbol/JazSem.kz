import type {
  EnrollmentSummary,
  SubmissionDetails,
  GroupDetails,
} from "../../entities/learning";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ArrowUpRight, BookOpen } from "lucide-react";
import { useUser } from "../../app/Auth";
import { api } from "../../services/api";
import type { Page, Row } from "../../entities/types";
import { Empty, ErrorState, Loading, ProgressBar } from "../../components/UI";
import { AdminDashboard } from "./AdminDashboard";

export function Dashboard() {
  const user = useUser();
  return user.role === "ADMIN" ? <AdminDashboard /> : <LearningDashboard />;
}

function LearningDashboard() {
  const user = useUser();
  const { t, i18n } = useTranslation();
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
    queryFn: () => api<Page<Row>>("assignments/?ordering=deadline&due=future"),
  });
  const reviews = useQuery({
    queryKey: ["submissions", "inbox"],
    queryFn: ({ signal }) =>
      api<Page<SubmissionDetails>>(
        "submissions/?pending=true",
        "GET",
        undefined,
        signal,
      ),
    enabled: user.role === "TEACHER",
  });
  const groups = useQuery({
    queryKey: ["groups", "dashboard"],
    queryFn: ({ signal }) =>
      api<Page<GroupDetails>>(
        "groups/?status=ACTIVE",
        "GET",
        undefined,
        signal,
      ),
    enabled: user.role === "TEACHER",
  });
  const learning = useQuery({
    queryKey: ["enrollments", "dashboard"],
    queryFn: ({ signal }) =>
      api<Page<EnrollmentSummary>>(
        "enrollments/summaries/",
        "GET",
        undefined,
        signal,
      ),
    enabled: user.role === "STUDENT",
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            {new Date().toLocaleDateString(
              i18n.language === "kk" ? "kk-KZ" : "ru-RU",
              {
                day: "numeric",
                month: "long",
                year: "numeric",
              },
            )}
          </span>
          <h1>
            {t("greeting")}, {user.first_name || user.email.split("@")[0]}{" "}
            <span className="greeting-dot">.</span>
          </h1>
          <p className="muted">{t("welcome")}</p>
        </div>
        {user.role !== "STUDENT" && (
          <Link className="button primary" to="/app/courses?create=1">
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
            to={
              user.role === "STUDENT" ? "/app/courses" : "/app/courses?create=1"
            }
          >
            {" "}
            {t(user.role === "STUDENT" ? "continue" : "createCourse")}{" "}
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
      {user.role === "TEACHER" && (
        <section className="panel">
          <div className="section-heading">
            <h2>{t("ux.reviewQueue")}</h2>
            <Link to="/app/submissions?pending=true">{t("all")} ↗</Link>
          </div>
          {reviews.isPending ? (
            <Loading />
          ) : reviews.error ? (
            <ErrorState
              error={reviews.error}
              retry={() => void reviews.refetch()}
            />
          ) : !reviews.data.results.length ? (
            <Empty />
          ) : (
            reviews.data.results.slice(0, 5).map((row) => (
              <Link
                className="learning-row"
                key={row.id}
                to={`/app/submissions/${row.id}`}
              >
                <div>
                  <h3>{row.assignment_title}</h3>
                  <small>
                    {row.student_name} · {t(row.status)}
                  </small>
                </div>
                <ArrowUpRight />
              </Link>
            ))
          )}
        </section>
      )}
      {user.role === "STUDENT" && (
        <section className="panel">
          <h2>{t("continue")}</h2>
          {learning.isPending ? (
            <Loading />
          ) : learning.error ? (
            <ErrorState
              error={learning.error}
              retry={() => void learning.refetch()}
            />
          ) : !learning.data.results.length ? (
            <Empty />
          ) : (
            learning.data.results.slice(0, 4).map((row) => (
              <article key={row.id}>
                <Link
                  className="learning-row"
                  to={`/app/courses/${row.course}`}
                >
                  <h3>{row.course_title}</h3>
                  <span>{row.progress.percent}% →</span>
                </Link>
                <ProgressBar value={row.progress.percent} />
              </article>
            ))
          )}
        </section>
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
          {assignments.isPending ? (
            <Loading />
          ) : assignments.error ? (
            <ErrorState
              error={assignments.error}
              retry={() => void assignments.refetch()}
            />
          ) : assignments.data.results.length ? (
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
                      ? new Date(String(a.deadline)).toLocaleString(
                          i18n.language,
                        )
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
      {user.role === "TEACHER" && (
        <section className="panel">
          <div className="section-heading">
            <h2>{t("ux.myGroups")}</h2>
            <Link to="/app/groups">{t("all")}</Link>
          </div>
          {groups.isPending ? (
            <Loading />
          ) : groups.error ? (
            <ErrorState
              error={groups.error}
              retry={() => void groups.refetch()}
            />
          ) : !groups.data.results.length ? (
            <Empty />
          ) : (
            groups.data.results.slice(0, 5).map((group) => (
              <Link
                className="learning-row"
                key={group.id}
                to={`/app/groups/${group.id}`}
              >
                {group.name}
                <ArrowUpRight />
              </Link>
            ))
          )}
        </section>
      )}
    </>
  );
}
