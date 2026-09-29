import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { Plus, Search, ArrowUpRight } from "lucide-react";
import type { Page, Row } from "../../entities/types";
import { api } from "../../services/api";
import { Badge, Empty, ErrorState, Loading, Modal } from "../../components/UI";
import { useUser } from "../../app/Auth";
import { useAction } from "../../hooks/useAction";
import { RecordForm } from "./RecordForm";
import { fields } from "./fields";
import { RecordDetails } from "./RecordDetails";
import { ActivityCreate, CourseCreate } from "./CreateLearning";

export function ResourcePage({ resource }: { resource: string }) {
  const { t, i18n } = useTranslation();
  const user = useUser();
  const action = useAction();
  const [params, setParams] = useSearchParams();
  const role =
    resource === "users" &&
    ["TEACHER", "STUDENT"].includes(params.get("role") || "")
      ? params.get("role")!
      : "";
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [edit, setEdit] = useState<Row | null | undefined>();
  const [confirm, setConfirm] = useState<{ path: string; body?: unknown }>();
  const [detail, setDetail] = useState<Row>();
  const query = useQuery({
    queryKey: [resource, page, search, role],
    queryFn: () =>
      api<Page<Row>>(
        `${resource}/?page=${page}&search=${encodeURIComponent(search)}${role ? `&role=${role}` : ""}`,
      ),
  });
  const canCreate =
    user.role !== "STUDENT" &&
    Boolean(fields[resource]) &&
    [
      "users",
      "courses",
      "groups",
      "disciplines",
      "content",
      "assignments",
      "tests",
    ].includes(resource) &&
    ((resource !== "disciplines" && resource !== "content") ||
      user.role === "ADMIN");
  const creating =
    edit === null ||
    (edit === undefined && params.get("create") === "1" && canCreate);
  const closeCreate = () => {
    setEdit(undefined);
    setParams(
      (p) => {
        p.delete("create");
        return p;
      },
      { replace: true },
    );
  };
  const createLabel =
    resource === "courses"
      ? "createCourse"
      : resource === "assignments"
        ? "workspace.createAssignment"
        : resource === "tests"
          ? "workspace.createTest"
          : resource === "users" && role
            ? `workspace.${role === "TEACHER" ? "addTeacher" : "addStudent"}`
            : "create";
  const hint =
    user.role !== "STUDENT"
      ? (
          {
            courses: "courseListHint",
            users: "usersHint",
            groups: "groupsHint",
            disciplines: "disciplinesHint",
          } as Record<string, string>
        )[resource]
      : undefined;
  const title =
    resource === "ai-usage"
      ? "usage"
      : resource === "users" && user.role === "TEACHER"
        ? "students"
        : resource;
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">JAZSEM / {t("app")}</span>
          <h1>
            {t(
              resource === "courses" && user.role === "ADMIN"
                ? "workspace.courses"
                : title,
            )}
          </h1>
          <p className="muted">
            {hint
              ? t(`workspace.${hint}`)
              : `${query.data?.count ?? "—"} ${t("all").toLowerCase()}`}
          </p>
        </div>
        {canCreate && (
          <button className="primary" onClick={() => setEdit(null)}>
            <Plus size={18} />
            {t(createLabel)}
          </button>
        )}
      </div>
      {user.role !== "STUDENT" &&
        ["assignments", "tests"].includes(resource) && (
          <section className="help-card">
            <div>
              <strong>{t("activityAuthoringTitle")}</strong>
              <p>{t("activityAuthoringHint")}</p>
            </div>
            <Link className="button" to="/app/courses">
              {t("openCourseBuilder")} <ArrowUpRight size={18} />
            </Link>
          </section>
        )}
      {["content", "audit"].includes(resource) && (
        <section className="help-card">
          <div>
            <strong>{t(resource + "HelpTitle")}</strong>
            <p>{t(resource + "Help")}</p>
          </div>
        </section>
      )}
      <div className="toolbar">
        <Search size={18} />
        <input
          aria-label={t("search")}
          placeholder={t("search")}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
        />
      </div>
      {resource === "users" && user.role === "ADMIN" && (
        <div className="people-filters" aria-label={t("workspace.people")}>
          {[
            ["", "workspace.allPeople"],
            ["TEACHER", "teachers"],
            ["STUDENT", "students"],
          ].map(([value, label]) => (
            <button
              key={value}
              aria-pressed={role === value}
              onClick={() => {
                setPage(1);
                setParams((p) => {
                  if (value) p.set("role", value);
                  else p.delete("role");
                  return p;
                });
              }}
            >
              {t(label)}
            </button>
          ))}
        </div>
      )}
      {action.feedback}
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : !query.data.results.length ? (
        <Empty>
          {canCreate && (
            <button onClick={() => setEdit(null)}>{t(createLabel)}</button>
          )}
        </Empty>
      ) : (
        <div className={resource === "courses" ? "course-grid" : "record-list"}>
          {query.data.results.map((row, index) => (
            <article
              className={resource === "courses" ? "course-card" : "record-row"}
              key={row.id}
            >
              {resource === "courses" && (
                <div className={"course-cover cover-" + (index % 3)}>
                  <span>J.</span>
                  <Badge>
                    {String(row.default_language || "RU").toUpperCase()}
                  </Badge>
                </div>
              )}
              <div className="record-body">
                <div>
                  <Badge>
                    {String(row.status || row.role || row.type || "")}
                  </Badge>
                  <h3>
                    {String(
                      row.title ||
                        row.name ||
                        row.email ||
                        row.action ||
                        row.operation ||
                        t("details"),
                    )}
                  </h3>
                  {row.description != null && (
                    <p className="muted">{String(row.description)}</p>
                  )}
                  {row.message != null && <p>{String(row.message)}</p>}
                  {row.score != null && (
                    <strong>{String(row.score)} / 100</strong>
                  )}
                  {row.created_at != null && (
                    <small className="muted">
                      {new Date(String(row.created_at)).toLocaleDateString(
                        i18n.language === "kk" ? "kk-KZ" : "ru-RU",
                      )}
                    </small>
                  )}
                </div>
                <div className="row-actions">
                  {resource === "notifications" &&
                    typeof row.link === "string" &&
                    row.link.startsWith("/app/") && (
                      <Link className="button" to={row.link}>
                        {t("continue")} <ArrowUpRight size={16} />
                      </Link>
                    )}
                  {resource === "courses" ? (
                    <Link className="button" to={"/app/courses/" + row.id}>
                      {t(user.role === "STUDENT" ? "continue" : "builder")}
                      <ArrowUpRight size={16} />
                    </Link>
                  ) : (
                    <button onClick={() => setDetail(row)}>
                      {t("details")}
                    </button>
                  )}
                  {user.role !== "STUDENT" &&
                    ["assignments", "tests"].includes(resource) &&
                    typeof row.course_id === "string" && (
                      <Link
                        className="button"
                        to={`/app/courses/${row.course_id}?version=${row.course_version_id}&activity=${row.id}`}
                      >
                        {t("workspace.editing")} <ArrowUpRight size={16} />
                      </Link>
                    )}
                  {canCreate &&
                    !["assignments", "tests"].includes(resource) && (
                      <button onClick={() => setEdit(row)}>{t("edit")}</button>
                    )}
                  {["courses", "groups", "disciplines"].includes(resource) &&
                    user.role !== "STUDENT" &&
                    (resource !== "disciplines" || user.role === "ADMIN") && (
                      <button
                        className="quiet"
                        onClick={() =>
                          setConfirm({ path: `${resource}/${row.id}/archive/` })
                        }
                      >
                        {t("archive")}
                      </button>
                    )}
                  {resource === "notifications" && !row.is_read && (
                    <button
                      onClick={() =>
                        void action.run(`notifications/${row.id}/read/`)
                      }
                    >
                      {t("read")}
                    </button>
                  )}
                  {resource === "users" && user.role !== "STUDENT" && (
                    <button
                      className="danger"
                      onClick={() =>
                        setConfirm({ path: `users/${row.id}/deactivate/` })
                      }
                    >
                      {t("archive")}
                    </button>
                  )}
                  {resource === "tests" && user.role === "STUDENT" && (
                    <Link className="button" to={"/app/tests/" + row.id}>
                      {t("start")}
                    </Link>
                  )}
                  {resource === "assignments" && user.role === "STUDENT" && (
                    <Link className="button" to={"/app/assignments/" + row.id}>
                      {t("submit")}
                    </Link>
                  )}
                  {resource === "submissions" && user.role !== "STUDENT" && (
                    <Link className="button" to={"/app/submissions/" + row.id}>
                      {t("grade")}
                    </Link>
                  )}
                  {resource === "groups" && (
                    <Link className="button" to={"/app/groups/" + row.id}>
                      {t("members")}
                    </Link>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
      {query.data && query.data.count > 25 && (
        <div className="pagination">
          <button
            disabled={!query.data.previous}
            onClick={() => setPage(page - 1)}
          >
            {t("back")}
          </button>
          <span>{page}</span>
          <button disabled={!query.data.next} onClick={() => setPage(page + 1)}>
            {t("next")}
          </button>
        </div>
      )}
      {(edit || creating) && (
        <Modal title={t(edit ? "edit" : createLabel)} onClose={closeCreate}>
          {creating && resource === "courses" ? (
            <CourseCreate onClose={closeCreate} />
          ) : creating &&
            (resource === "assignments" || resource === "tests") ? (
            <ActivityCreate resource={resource} onClose={closeCreate} />
          ) : (
            <RecordForm
              resource={resource}
              initial={edit || undefined}
              defaults={resource === "users" && role ? { role } : {}}
              onDone={closeCreate}
            />
          )}
        </Modal>
      )}
      {confirm && (
        <Modal title={t("confirm")} onClose={() => setConfirm(undefined)}>
          <p>{t("confirmText")}</p>
          <button
            className="danger"
            disabled={action.pending}
            onClick={async () => {
              await action.run(confirm.path, confirm.body);
              setConfirm(undefined);
            }}
          >
            {t("confirm")}
          </button>
        </Modal>
      )}
      {detail && (
        <Modal title={t("details")} onClose={() => setDetail(undefined)}>
          <RecordDetails row={detail} />
        </Modal>
      )}
    </>
  );
}
