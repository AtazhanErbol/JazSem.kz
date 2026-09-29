import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  ArrowUpRight,
  BookOpen,
  FileText,
  ListChecks,
  Plus,
  Users,
  GraduationCap,
  Layers,
  CircleHelp,
} from "lucide-react";
import { api } from "../../services/api";
import type { Page, Row } from "../../entities/types";
import { Badge, ErrorState, Loading } from "../../components/UI";

export function AdminDashboard() {
  const { t } = useTranslation();
  const stats = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Record<string, number>>("dashboard/"),
  });
  const courses = useQuery({
    queryKey: ["courses", "admin-dashboard"],
    queryFn: () => api<Page<Row>>("courses/?ordering=-updated_at"),
  });
  return (
    <div className="admin-workspace">
      <div className="page-heading">
        <div>
          <span className="eyebrow">JAZSEM / {t("ADMIN")}</span>
          <h1>{t("workspace.home")}</h1>
          <p className="muted">{t("workspace.homeHint")}</p>
        </div>
        <Link className="button" to="/app/guide">
          <CircleHelp size={18} />
          {t("workspace.guide")}
        </Link>
      </div>
      <section aria-labelledby="create-heading">
        <div className="section-heading">
          <h2 id="create-heading">{t("workspace.startTitle")}</h2>
          <span className="muted">{t("workspace.manual")}</span>
        </div>
        <div className="creation-grid">
          {(
            [
              ["courses", "createCourse", "courseDescription", BookOpen],
              [
                "assignments",
                "workspace.createAssignment",
                "assignmentDescription",
                FileText,
              ],
              ["tests", "workspace.createTest", "testDescription", ListChecks],
            ] as const
          ).map(([path, label, description, Icon]) => (
            <Link
              key={path}
              to={`/app/${path}?create=1`}
              className={`creation-card ${path === "courses" ? "featured" : ""}`}
            >
              <div className="creation-icons">
                <span className="creation-icon">
                  <Icon size={24} />
                </span>
                <Plus size={19} />
              </div>
              <h3>{t(label)}</h3>
              <p>{t(`workspace.${description}`)}</p>
              <ArrowUpRight className="creation-arrow" size={20} />
            </Link>
          ))}
        </div>
      </section>
      <section className="journey-panel">
        <div className="section-heading">
          <h2>{t("workspace.journeyTitle")}</h2>
          <Link to="/app/guide">{t("details")} ↗</Link>
        </div>
        <Journey compact />
      </section>
      {stats.isPending ? (
        <Loading />
      ) : stats.error ? (
        <ErrorState error={stats.error} />
      ) : (
        <div className="workspace-stats">
          {(
            [
              ["courses", "workspace.courses", "/app/courses"],
              ["teachers", "teachers", "/app/users?role=TEACHER"],
              ["students", "students", "/app/users?role=STUDENT"],
            ] as const
          ).map(([key, label, to]) => (
            <Link key={key} to={to}>
              <span>{t(label)}</span>
              <strong>{stats.data[key] ?? 0}</strong>
              <ArrowUpRight size={16} />
            </Link>
          ))}
        </div>
      )}
      <div className="dashboard-columns">
        <section>
          <div className="section-heading">
            <h2>{t("workspace.recentCourses")}</h2>
            <Link to="/app/courses">{t("all")} ↗</Link>
          </div>
          {courses.isPending ? (
            <Loading />
          ) : courses.error ? (
            <ErrorState error={courses.error} />
          ) : !courses.data.results.length ? (
            <div className="workspace-empty">
              <BookOpen />
              <h3>{t("workspace.noCourses")}</h3>
              <p>{t("workspace.noCoursesHint")}</p>
              <Link className="button primary" to="/app/courses?create=1">
                {t("createCourse")}
              </Link>
            </div>
          ) : (
            courses.data.results.slice(0, 4).map((course) => (
              <Link
                className="learning-row"
                to={`/app/courses/${course.id}`}
                key={course.id}
              >
                <span className="course-icon">
                  <BookOpen />
                </span>
                <div>
                  <h3>{String(course.title)}</h3>
                  <Badge>{String(course.default_language).toUpperCase()}</Badge>
                </div>
                <ArrowUpRight size={18} />
              </Link>
            ))
          )}
        </section>
        <section className="panel people-panel">
          <h2>{t("workspace.people")}</h2>
          <p className="muted">{t("workspace.peopleHint")}</p>
          {(
            [
              ["users?create=1&role=TEACHER", "addTeacher", GraduationCap],
              ["users?create=1&role=STUDENT", "addStudent", Users],
              ["groups?create=1", "createGroup", Layers],
            ] as const
          ).map(([path, label, Icon]) => (
            <Link className="people-action" key={path} to={`/app/${path}`}>
              <Icon size={19} />
              <span>{t(`workspace.${label}`)}</span>
              <Plus size={16} />
            </Link>
          ))}
        </section>
      </div>
    </div>
  );
}

function Journey({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();
  return (
    <ol className={`workspace-journey ${compact ? "compact" : ""}`}>
      {[
        ["prepare", "/app/disciplines", "workspace.openDisciplines"],
        ["build", "/app/courses?create=1", "createCourse"],
        ["share", "/app/courses", "workspace.courses"],
        ...(!compact ? [["results", "/app/submissions", "submissions"]] : []),
      ].map(([step, to, label], index) => (
        <li key={step}>
          <span className="workspace-step-number">0{index + 1}</span>
          <div>
            <h3>{t(`workspace.${step}Title`)}</h3>
            <p>{t(`workspace.${step}Text`)}</p>
            <Link to={to}>
              {t(label)} <span aria-hidden="true">↗</span>
            </Link>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function WorkspaceGuide() {
  const { t } = useTranslation();
  return (
    <div className="workspace-guide">
      <div className="page-heading">
        <div>
          <h1>{t("workspace.guide")}</h1>
          <p className="muted">{t("workspace.guideIntro")}</p>
        </div>
        <Link className="button primary" to="/app/courses?create=1">
          + {t("createCourse")}
        </Link>
      </div>
      <section className="panel">
        <Journey />
      </section>
      <section className="panel">
        <h2>{t("workspace.glossaryTitle")}</h2>
        <dl className="workspace-glossary">
          {(
            [
              ["disciplines", "disciplineMeaning"],
              ["workspace.courses", "courseMeaning"],
              ["content", "contentMeaning"],
              ["audit", "auditMeaning"],
              ["ai", "aiMeaning"],
            ] as const
          ).map(([label, description]) => (
            <div key={label}>
              <dt>{t(label)}</dt>
              <dd>{t(`workspace.${description}`)}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
