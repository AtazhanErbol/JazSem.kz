import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BookOpen, Check, ChevronRight, Plus, FileText } from "lucide-react";
import type { Activity, Page, Progress, Row, Tree } from "../../entities/types";
import { api, allRows } from "../../services/api";
import {
  Badge,
  Empty,
  ErrorState,
  Loading,
  Modal,
  ProgressBar,
} from "../../components/UI";
import { useUser } from "../../app/Auth";
import { useAction } from "../../hooks/useAction";
import { RecordForm } from "../manage/RecordForm";

interface Editor {
  resource: string;
  initial?: Row;
  fixed?: Record<string, unknown>;
}
export function CoursePage() {
  const { id } = useParams();
  const user = useUser();
  const { t } = useTranslation();
  const action = useAction();
  const [version, setVersion] = useState("");
  const [selected, setSelected] = useState<{ type: string; item: Activity }>();
  const [editor, setEditor] = useState<Editor>();
  const [confirm, setConfirm] = useState<string>();
  const [student, setStudent] = useState("");
  const [group, setGroup] = useState("");
  const teacher = user.role !== "STUDENT";
  const query = useQuery({
    queryKey: ["tree", id, version],
    queryFn: () =>
      api<Tree>(`courses/${id}/tree/${version ? "?version=" + version : ""}`),
  });
  const versions = useQuery({
    queryKey: ["versions", id],
    queryFn: () => api<Row[]>(`courses/${id}/versions/`),
    enabled: teacher,
  });
  const students = useQuery({
    queryKey: ["options", "students"],
    queryFn: () => allRows("users/?role=STUDENT"),
    enabled: teacher,
  });
  const groups = useQuery({
    queryKey: ["options", "groups"],
    queryFn: () => allRows("groups/"),
    enabled: teacher,
  });
  const enrollments = useQuery({
    queryKey: ["enrollments", id],
    queryFn: () => api<Page<Row>>(`enrollments/?course=${id}`),
    enabled: !teacher,
  });
  const enrollment = enrollments.data?.results[0];
  const progress = useQuery({
    queryKey: ["progress", enrollment?.id],
    queryFn: () => api<Progress>(`enrollments/${enrollment!.id}/progress/`),
    enabled: !!enrollment,
  });
  if (query.isPending) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const data = query.data;
  const editable =
    teacher && ["DRAFT", "REVIEW"].includes(String(data.version.status));
  const edit = (resource: string, initial: Row) =>
    setEditor({ resource, initial });
  const add = (resource: string, fixed: Record<string, unknown>) =>
    setEditor({ resource, fixed });
  const controls = (resource: string, row: Row) => (
    <div className="mini-actions">
      <button onClick={() => edit(resource, row)}>{t("edit")}</button>
      <button
        className="danger-text"
        onClick={() => setConfirm(`delete:${resource}/${row.id}/`)}
      >
        {t("delete")}
      </button>
    </div>
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <Link className="eyebrow" to="/app/courses">
            ← {t("courses")}
          </Link>
          <h1>{String(data.course.title)}</h1>
          <Badge>
            {t(String(data.version.status))} · v
            {String(data.version.version_number)}
          </Badge>
        </div>
        <div className="row-actions">
          {teacher && (
            <>
              <select
                aria-label={t("version")}
                value={version || data.version.id}
                onChange={(e) => setVersion(e.target.value)}
              >
                {versions.data?.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{String(v.version_number)} · {t(String(v.status))}
                  </option>
                ))}
              </select>
              <button
                disabled={action.pending}
                onClick={async () => {
                  const v = await action.run<Row>(`courses/${id}/duplicate/`, {
                    version: data.version.id,
                  });
                  if (v) setVersion(v.id);
                }}
              >
                {t("newVersion")}
              </button>
              {editable && (
                <button
                  className="primary"
                  onClick={() => setConfirm("publish")}
                >
                  {t("publish")}
                </button>
              )}
            </>
          )}
        </div>
      </div>
      {action.feedback}
      {teacher && !editable && <p className="notice">{t("immutable")}</p>}
      {!teacher && progress.data && (
        <div className="course-progress">
          <span>
            {t("progress")} {progress.data.percent}%
          </span>
          <ProgressBar value={progress.data.percent} />
        </div>
      )}
      <div className="course-layout">
        <aside className="course-outline">
          <h3>
            <BookOpen size={18} />
            {t("outline")}
          </h3>
          {data.weeks.map((week) => (
            <section key={week.id}>
              <div className="outline-week">
                <strong>
                  {week.number}. {week.title}
                </strong>
                {editable && controls("weeks", week)}
              </div>
              {week.topics.map((topic) => (
                <div className="outline-topic" key={topic.id}>
                  <button
                    onClick={() => setSelected({ type: "topic", item: topic })}
                  >
                    <ChevronRight size={14} />
                    {topic.title}
                  </button>
                  {editable && controls("topics", topic)}
                  {(["materials", "assignments", "tests"] as const).map(
                    (type) =>
                      topic[type].map((item) => (
                        <button
                          key={item.id}
                          className={
                            selected?.item.id === item.id
                              ? "outline-item active"
                              : "outline-item"
                          }
                          onClick={() => setSelected({ type, item })}
                        >
                          {type === "materials" &&
                          progress.data?.materials.includes(item.id) ? (
                            <Check size={14} />
                          ) : (
                            <FileText size={14} />
                          )}{" "}
                          {item.title}
                        </button>
                      )),
                  )}
                  {editable && (
                    <div className="builder-adds">
                      <button
                        onClick={() => add("materials", { topic: topic.id })}
                      >
                        + {t("materials")}
                      </button>
                      <button
                        onClick={() => add("assignments", { topic: topic.id })}
                      >
                        + {t("assignments")}
                      </button>
                      <button onClick={() => add("tests", { topic: topic.id })}>
                        + {t("tests")}
                      </button>
                    </div>
                  )}
                </div>
              ))}
              {editable && (
                <button
                  className="text-button"
                  onClick={() => add("topics", { week: week.id })}
                >
                  + {t("addTopic")}
                </button>
              )}
            </section>
          ))}
          {editable && (
            <button
              onClick={() => add("weeks", { course_version: data.version.id })}
            >
              <Plus size={16} />
              {t("addWeek")}
            </button>
          )}
        </aside>
        <section className="content-pane">
          {selected ? (
            <>
              <span className="eyebrow">{t(selected.type)}</span>
              <h2>{selected.item.title}</h2>
              <div className="prose">
                {selected.item.content ||
                  selected.item.instructions ||
                  String(selected.item.description || "")}
              </div>
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
                  target="_blank"
                  rel="noreferrer"
                  href={selected.item.external_url}
                >
                  {t("details")} ↗
                </a>
              )}
              {editable &&
                selected.type !== "topic" &&
                controls(selected.type, selected.item)}
              {["materials", "topic"].includes(selected.type) && !teacher && (
                <button
                  className="primary"
                  disabled={
                    action.pending ||
                    (selected.type === "topic"
                      ? progress.data?.read_topics
                      : progress.data?.materials
                    )?.includes(selected.item.id)
                  }
                  onClick={() =>
                    void action.run(
                      `${selected.type === "topic" ? "topics" : "materials"}/${selected.item.id}/complete/`,
                    )
                  }
                >
                  <Check size={18} />
                  {t(
                    (selected.type === "topic"
                      ? progress.data?.read_topics
                      : progress.data?.materials
                    )?.includes(selected.item.id)
                      ? "completed"
                      : "complete",
                  )}
                </button>
              )}
              {selected.type === "assignments" && !teacher && (
                <Link
                  className="button primary"
                  to={"/app/assignments/" + selected.item.id}
                >
                  {t("submit")}
                </Link>
              )}
              {selected.type === "tests" && !teacher && (
                <Link
                  className="button primary"
                  to={"/app/tests/" + selected.item.id}
                >
                  {t("start")}
                </Link>
              )}
              {selected.type === "tests" && teacher && (
                <>
                  {selected.item.questions?.map((question) => (
                    <div className="question-editor" key={question.id}>
                      <h3>{question.text}</h3>
                      {editable && controls("questions", question)}
                      {question.options.map((option) => (
                        <div className="option-editor" key={option.id}>
                          <span>
                            {option.is_correct ? "✓" : "○"} {option.text}
                          </span>
                          {editable && controls("options", option)}
                        </div>
                      ))}
                      {editable && (
                        <button
                          onClick={() =>
                            add("options", { question: question.id })
                          }
                        >
                          + {t("addOption")}
                        </button>
                      )}
                    </div>
                  ))}
                  {editable && (
                    <button
                      onClick={() =>
                        add("questions", { test: selected.item.id })
                      }
                    >
                      + {t("addQuestion")}
                    </button>
                  )}
                </>
              )}
              {teacher &&
                Array.isArray(selected.item.source_chunks) &&
                selected.item.source_chunks.length > 0 && (
                  <div className="sources">
                    <h3>{t("sources")}</h3>
                    {(selected.item.source_chunks as string[]).map((chunk) => (
                      <Citation key={chunk} id={chunk} />
                    ))}
                  </div>
                )}
            </>
          ) : (
            <div className="course-intro">
              <span className="course-icon">
                <BookOpen size={32} />
              </span>
              <h2>{String(data.course.title)}</h2>
              <p>{String(data.course.description)}</p>
              <p className="muted">{t("noSelection")}</p>
              {!data.weeks.length && <Empty />}
            </div>
          )}
        </section>
      </div>
      {teacher && (
        <div className="dashboard-columns">
          <section className="panel">
            <h2>{t("grading")}</h2>
            {data.components.map((c) => (
              <div className="record-row" key={c.id}>
                <span>
                  {t(String(c.kind))} · {String(c.weight)}%
                </span>
                {editable && controls("grading-components", c)}
              </div>
            ))}
            {editable && (
              <button
                onClick={() =>
                  data.scheme
                    ? add("grading-components", { scheme: data.scheme.id })
                    : add("grading-schemes", {
                        course_version: data.version.id,
                      })
                }
              >
                + {t(data.scheme ? "addComponent" : "grading")}
              </button>
            )}
          </section>
          <section className="panel">
            <h2>{t("assign")}</h2>
            <label>
              {t("student")}
              <select
                value={student}
                onChange={(e) => setStudent(e.target.value)}
              >
                <option value="">—</option>
                {students.data?.map((s) => (
                  <option key={s.id} value={s.id}>
                    {String(s.first_name)} {String(s.last_name)} ·{" "}
                    {String(s.email)}
                  </option>
                ))}
              </select>
            </label>
            <button
              disabled={!student || action.pending}
              onClick={() =>
                void action.run(`courses/${id}/assign/`, { student })
              }
            >
              {t("assign")}
            </button>
            <label>
              {t("groups")}
              <select value={group} onChange={(e) => setGroup(e.target.value)}>
                <option value="">—</option>
                {groups.data?.map((g) => (
                  <option key={g.id} value={g.id}>
                    {String(g.name)}
                  </option>
                ))}
              </select>
            </label>
            <button
              disabled={!group || action.pending}
              onClick={() =>
                void action.run(`groups/${group}/assign/`, { course: id })
              }
            >
              {t("assign")}
            </button>
          </section>
        </div>
      )}
      {editor && (
        <Modal
          title={t(editor.initial ? "edit" : "create")}
          onClose={() => setEditor(undefined)}
        >
          <RecordForm
            resource={editor.resource}
            initial={editor.initial}
            fixed={editor.fixed}
            onDone={() => {
              setEditor(undefined);
              setSelected(undefined);
            }}
          />
        </Modal>
      )}
      {confirm && (
        <Modal title={t("confirm")} onClose={() => setConfirm(undefined)}>
          <p>{t("confirmText")}</p>
          <button
            className="primary"
            disabled={action.pending}
            onClick={async () => {
              if (confirm === "publish")
                await action.run(`courses/${id}/publish/`, {
                  version: data.version.id,
                });
              else await action.run(confirm.slice(7), undefined, "DELETE");
              setConfirm(undefined);
              setSelected(undefined);
            }}
          >
            {t("confirm")}
          </button>
        </Modal>
      )}
    </>
  );
}
function Citation({ id }: { id: string }) {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: ["chunk", id],
    queryFn: () => api<Row>(`chunks/${id}/`),
  });
  return query.data ? (
    <details>
      <summary>
        {t("source")} · {String(query.data.page_number)}
      </summary>
      <p>{String(query.data.content)}</p>
    </details>
  ) : null;
}
