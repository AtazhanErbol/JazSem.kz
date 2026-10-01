import { TestImport } from "./TestImport";
import { GradingWeights } from "./GradingWeights";
import { CourseSharing } from "./CourseSharing";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  useParams,
  Link,
  useSearchParams,
  useNavigate,
} from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  BookOpen,
  Check,
  ChevronRight,
  Plus,
  FileText,
  ClipboardList,
  ListChecks,
  Search,
} from "lucide-react";
import type { Activity, Row, Tree } from "../../entities/types";
import { api } from "../../services/api";
import { Badge, Empty, ErrorState, Loading, Modal } from "../../components/UI";
import { useAction } from "../../hooks/useAction";
import { RecordForm } from "../manage/RecordForm";

interface Editor {
  resource: string;
  initial?: Row;
  fixed?: Record<string, unknown>;
  defaults?: Record<string, unknown>;
}
export function CourseBuilder() {
  const { id } = useParams();
  const { t } = useTranslation();
  const action = useAction();
  const navigate = useNavigate();
  const [upgrade, setUpgrade] = useState<{
    students: number;
    groups: number;
    version_number: number;
    version: string;
  }>();
  const [outlineSearch, setOutlineSearch] = useState("");
  const [outlineKind, setOutlineKind] = useState("all");
  const [weightsOpen, setWeightsOpen] = useState(false);
  const [deleteDraft, setDeleteDraft] = useState(false);
  const [deleteName, setDeleteName] = useState("");
  const [params, setParams] = useSearchParams();
  const version = params.get("version") || "";
  const setVersion = (value: string) => {
    setSelected(undefined);
    setParams((p) => {
      p.set("version", value);
      p.delete("activity");
      return p;
    });
  };
  const [selection, setSelected] = useState<{ type: string; item: Activity }>();
  const [editor, setEditor] = useState<Editor>();
  const [confirm, setConfirm] = useState<string>();
  const query = useQuery({
    queryKey: ["tree", id, version],
    queryFn: ({ signal }) =>
      api<Tree>(
        `courses/${id}/tree/${version ? "?version=" + version : ""}`,
        "GET",
        undefined,
        signal,
      ),
  });
  const versions = useQuery({
    queryKey: ["versions", id],
    queryFn: ({ signal }) =>
      api<Row[]>(`courses/${id}/versions/`, "GET", undefined, signal),
  });
  if (query.isPending) return <Loading />;
  if (query.error)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  const data = query.data;
  const topics = data.weeks.flatMap((week) => week.topics);
  const selectedItem: Activity | undefined =
    selection &&
    (selection.type === "topic"
      ? topics
      : topics.flatMap((topic) => [
          ...topic.materials,
          ...topic.assignments,
          ...topic.tests,
        ])
    ).find((item) => item.id === selection.item.id);
  const selected: { type: string; item: Activity } | undefined =
    selection && selectedItem
      ? { type: selection.type, item: selectedItem }
      : topics.find((topic) => topic.id === params.get("activity"))
        ? {
            type: "topic",
            item: topics.find((topic) => topic.id === params.get("activity"))!,
          }
        : topics
            .flatMap((topic) =>
              (["materials", "assignments", "tests"] as const).flatMap((type) =>
                topic[type].map((item) => ({ type, item })),
              ),
            )
            .find((entry) => entry.item.id === params.get("activity"));
  const needle = outlineSearch.trim().toLocaleLowerCase();
  const matches = (title: string) =>
    !needle || title.toLocaleLowerCase().includes(needle);
  const visibleWeeks = data.weeks
    .map((week) => ({
      ...week,
      topics: week.topics
        .map((topic) => {
          const parentMatch =
            !!needle && (matches(week.title) || matches(topic.title));
          return {
            ...topic,
            ...Object.fromEntries(
              (["materials", "assignments", "tests"] as const).map((kind) => [
                kind,
                topic[kind].filter(
                  (item) =>
                    (outlineKind === "all" || outlineKind === kind) &&
                    (parentMatch || matches(item.title)),
                ),
              ]),
            ),
          };
        })
        .filter(
          (topic) =>
            ((!needle || matches(week.title) || matches(topic.title)) &&
              outlineKind === "all") ||
            topic.materials.length +
              topic.assignments.length +
              topic.tests.length >
              0,
        ),
    }))
    .filter((week) => week.topics.length || (!needle && outlineKind === "all"));
  const choose = (type: string, item: Activity) => {
    setSelected({ type, item });
    setParams(
      (p) => {
        p.set("activity", item.id);
        return p;
      },
      { replace: true },
    );
    document
      .getElementById("course-content")
      ?.scrollIntoView({ block: "start" });
  };
  const editable = ["DRAFT", "REVIEW"].includes(String(data.version.status));
  const edit = (resource: string, initial: Row) =>
    setEditor({ resource, initial });
  const add = (resource: string, fixed: Record<string, unknown>) =>
    setEditor({ resource, fixed });
  const addWeek = () =>
    setEditor({
      resource: "weeks",
      fixed: { course_version: data.version.id },
      defaults: {
        number:
          Math.max(0, ...data.weeks.map((week) => Number(week.number))) + 1,
      },
    });
  const activityCount = topics.reduce(
    (n, topic) =>
      n +
      topic.materials.length +
      topic.assignments.length +
      topic.tests.length,
    0,
  );
  const gradableCount = topics.reduce(
    (n, topic) => n + topic.assignments.length + topic.tests.length,
    0,
  );
  const weightTotal = data.components.reduce((n, c) => n + Number(c.weight), 0);
  const published = data.version.status === "PUBLISHED";
  const draftName = `${data.course.title} · v${data.version.version_number}`;
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
            {editable && (
              <button className="primary" onClick={() => setConfirm("publish")}>
                {t("publish")}
              </button>
            )}
          </>
        </div>
      </div>
      {versions.isPending && <Loading />}
      {versions.error && (
        <ErrorState
          error={versions.error}
          retry={() => void versions.refetch()}
        />
      )}
      {action.feedback}
      <section
        className="panel version-actions"
        aria-label={t("versionActions")}
      >
        <h2>
          {t("versionActions")} · v{String(data.version.version_number)}
        </h2>
        {published && <p className="muted">{t("editPublishedHint")}</p>}
        <div className="row-actions">
          <button
            disabled={action.pending}
            onClick={async () => {
              const v = await action.run<Row>(
                `courses/${id}/${published ? "edit-draft" : "duplicate"}/`,
                {
                  version: data.version.id,
                },
              );
              if (v.ok) setVersion(v.data.id);
            }}
          >
            {t(published ? "editPublished" : "newVersion")}
          </button>
        </div>
      </section>
      {(editable || published) && (
        <div className="row-actions">
          <button
            className="danger-text"
            disabled={action.pending}
            onClick={() => {
              setDeleteName("");
              setDeleteDraft(true);
            }}
          >
            {t(published ? "deletePublished" : "deleteDraft")}
          </button>
        </div>
      )}
      {published && (
        <section className="panel">
          <h2>{t("upgradeStudentsTitle")}</h2>
          <p className="muted">{t("upgradeStudentsHint")}</p>
          <button
            className="primary"
            disabled={action.pending}
            onClick={async () => {
              const result = await action.run<{
                students: number;
                groups: number;
                version_number: number;
              }>(
                `courses/${id}/update-students-preview/`,
                { version: data.version.id },
                "POST",
                t("upgradeChecked"),
              );
              if (result.ok)
                setUpgrade({ ...result.data, version: data.version.id });
            }}
          >
            {t("upgradeStudents")}
          </button>
        </section>
      )}
      {upgrade && (
        <Modal
          title={t("upgradeStudents")}
          onClose={() => {
            if (!action.pending) setUpgrade(undefined);
          }}
        >
          <p>
            {t("upgradeSummary", {
              students: upgrade.students,
              groups: upgrade.groups,
              version: upgrade.version_number,
            })}
          </p>
          <p>{t("upgradeResultsHint")}</p>
          {action.error != null && <ErrorState error={action.error} />}
          <div className="form-actions">
            <button
              disabled={action.pending}
              onClick={() => setUpgrade(undefined)}
            >
              {t("cancel")}
            </button>
            <button
              className="primary"
              disabled={
                action.pending || (!upgrade.students && !upgrade.groups)
              }
              onClick={async () => {
                const result = await action.run(
                  `courses/${id}/update-students/`,
                  { version: upgrade.version },
                  "POST",
                  t("upgradeDone"),
                );
                if (result.ok) setUpgrade(undefined);
              }}
            >
              {t("confirm")}
            </button>
          </div>
        </Modal>
      )}
      {deleteDraft && (
        <Modal
          title={t(published ? "deletePublished" : "deleteDraft")}
          onClose={() => {
            if (!action.pending) setDeleteDraft(false);
          }}
        >
          <p>{t(published ? "deletePublishedHint" : "deleteDraftHint")}</p>
          <p>
            <strong>{draftName}</strong>
          </p>
          <label>
            {t("deleteDraftConfirm")}
            <input
              value={deleteName}
              disabled={action.pending}
              onChange={(e) => setDeleteName(e.target.value)}
              autoComplete="off"
            />
          </label>
          {action.error != null && <ErrorState error={action.error} />}
          <div className="form-actions">
            <button
              disabled={action.pending}
              onClick={() => setDeleteDraft(false)}
            >
              {t("cancel")}
            </button>
            <button
              className="danger"
              disabled={action.pending || deleteName !== draftName}
              onClick={async () => {
                const result = await action.run<{
                  course_deleted: boolean;
                  next_version: string;
                }>(
                  `courses/${id}/${published ? "delete-published" : "delete-draft"}/`,
                  {
                    version: data.version.id,
                    confirmation: deleteName,
                  },
                );
                if (result.ok) {
                  setDeleteDraft(false);
                  if (result.data.course_deleted) navigate("/app/courses");
                  else setVersion(result.data.next_version);
                }
              }}
            >
              {t(published ? "deletePublished" : "deleteDraft")}
            </button>
          </div>
        </Modal>
      )}
      {editable && (
        <section
          className="builder-checklist"
          aria-label={t("workspace.courseProgress")}
        >
          {[
            [
              "workspace.structure",
              "workspace.structureHelp",
              topics.length > 0,
              "#course-structure",
            ],
            [
              "workspace.activities",
              "workspace.activityHelp",
              activityCount > 0,
              "#course-content",
            ],
            [
              "grading",
              "workspace.gradingHelp",
              weightTotal === 100,
              "#course-grading",
            ],
            [
              "workspace.publishStep",
              "workspace.publishHelp",
              false,
              "#course-sharing",
            ],
          ].map(([label, hint, done, href], index) => (
            <a
              key={String(label)}
              href={String(href)}
              className={done ? "complete" : ""}
            >
              <span className="workspace-step-number">
                {done ? <Check size={16} /> : index + 1}
              </span>
              <div>
                <strong>{t(String(label))}</strong>
                <small>{t(String(hint))}</small>
              </div>
            </a>
          ))}
        </section>
      )}
      <div className="course-layout">
        <aside className="course-outline" id="course-structure">
          <h3>
            <BookOpen size={18} />
            {t("outline")}
          </h3>
          <div className="outline-tools">
            <label>
              <Search size={16} />
              <input
                aria-label={t("courseSearch")}
                placeholder={t("courseSearch")}
                value={outlineSearch}
                onChange={(e) => setOutlineSearch(e.target.value)}
              />
            </label>
            <select
              aria-label={t("courseFilter")}
              value={outlineKind}
              onChange={(e) => setOutlineKind(e.target.value)}
            >
              {["all", "materials", "assignments", "tests"].map((kind) => (
                <option key={kind} value={kind}>
                  {t(kind)}
                </option>
              ))}
            </select>
            <p className="muted">{t("courseNavigationHint")}</p>
          </div>
          {!visibleWeeks.length && <p>{t("noSearchResults")}</p>}
          {visibleWeeks.map((week) => (
            <section key={week.id}>
              <div className="outline-week">
                <span className="week-marker">
                  {t("week")} {week.number}
                </span>
                <strong>
                  {week.number}. {week.title}
                </strong>
                {editable && controls("weeks", week)}
              </div>
              {week.topics.map((topic) => (
                <div className="outline-topic" key={topic.id}>
                  <button onClick={() => choose("topic", topic)}>
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
                          onClick={() => choose(type, item)}
                        >
                          {type === "tests" ? (
                            <ListChecks size={17} />
                          ) : type === "assignments" ? (
                            <ClipboardList size={17} />
                          ) : (
                            <FileText size={17} />
                          )}{" "}
                          <span>
                            <small>{t(type)}</small>
                            {item.title}
                          </span>
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
            <button onClick={addWeek}>
              <Plus size={16} />
              {t("addWeek")}
            </button>
          )}
        </aside>
        <section className="content-pane" id="course-content">
          {selected ? (
            <>
              <p className="content-location">
                {
                  data.weeks.flatMap((w) =>
                    w.topics
                      .filter(
                        (topic) =>
                          topic.id === selected.item.id ||
                          [
                            ...topic.materials,
                            ...topic.assignments,
                            ...topic.tests,
                          ].some((item) => item.id === selected.item.id),
                      )
                      .map(
                        (topic) => `${t("week")} ${w.number} / ${topic.title}`,
                      ),
                  )[0]
                }
              </p>
              <span className="eyebrow">{t(selected.type)}</span>
              <h2>{selected.item.title}</h2>
              <div className="prose">
                {selected.item.content ||
                  selected.item.instructions ||
                  String(selected.item.description || "")}
              </div>
              {editable && selected.type === "topic" && (
                <div className="topic-create">
                  <h3>{t("workspace.topicEmptyTitle")}</h3>
                  <div className="row-actions">
                    {["materials", "assignments", "tests"].map((resource) => (
                      <button
                        key={resource}
                        onClick={() =>
                          add(resource, { topic: selected.item.id })
                        }
                      >
                        <Plus size={16} />
                        {t(resource)}
                      </button>
                    ))}
                  </div>
                </div>
              )}
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
              {editable && selected.type === "tests" && (
                <TestImport key={selected.item.id} id={selected.item.id} />
              )}
              {selected.type === "tests" && (
                <>
                  {editable && !!selected.item.questions?.length && (
                    <p className="muted">{t("workspace.testEmptyText")}</p>
                  )}
                  {editable && !selected.item.questions?.length && (
                    <div className="workspace-empty">
                      <h3>{t("workspace.testEmptyTitle")}</h3>
                      <p>{t("workspace.testEmptyText")}</p>
                    </div>
                  )}
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
              {Array.isArray(selected.item.source_chunks) &&
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
              {editable ? (
                <>
                  <h3>{t("workspace.courseEmptyTitle")}</h3>
                  <p className="muted">{t("workspace.courseEmptyText")}</p>
                  <div className="row-actions">
                    {!data.weeks.length ? (
                      <button className="primary" onClick={addWeek}>
                        + {t("addWeek")}
                      </button>
                    ) : !topics.length ? (
                      <button
                        className="primary"
                        onClick={() =>
                          add("topics", { week: data.weeks[0].id })
                        }
                      >
                        + {t("addTopic")}
                      </button>
                    ) : (
                      <button
                        onClick={() =>
                          setSelected({ type: "topic", item: topics[0] })
                        }
                      >
                        {t("workspace.activities")} →
                      </button>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <p className="muted">{t("noSelection")}</p>
                  {!data.weeks.length && <Empty />}
                </>
              )}
            </div>
          )}
        </section>
      </div>
      <div className="dashboard-columns">
        <section className="panel" id="course-grading">
          <h2>{t("grading")}</h2>
          <p
            className={
              weightTotal === 100 ? "grading-total complete" : "notice"
            }
          >
            {t("workspace.gradingTotal", { total: weightTotal })}
            {weightTotal !== 100 && <> · {t("weightsNeed100")}</>}
          </p>
          {editable && !data.components.length && (
            <div className="grading-helper">
              <p className="muted">
                {t(
                  gradableCount
                    ? "workspace.equalWeightsHint"
                    : "workspace.gradingNeedsActivity",
                )}
              </p>
              <button
                className="primary"
                disabled={!gradableCount || action.pending}
                onClick={() =>
                  void action.run(`courses/${id}/grading-preset/`, {
                    version: data.version.id,
                  })
                }
              >
                {t("workspace.equalWeights")}
              </button>
            </div>
          )}
          <p className="muted">{t("learningDisplay.weightHint")}</p>
          <div className="grading-components">
            {data.components.map((c) => (
              <div className="record-row" key={c.id}>
                <span>
                  <strong>{t(String(c.kind))}</strong>
                  <small>
                    {t("learningDisplay.weight")}: {String(c.weight)}%
                  </small>
                </span>
              </div>
            ))}
          </div>
          {editable && (
            <button
              className="contextual-action"
              onClick={() => setWeightsOpen(true)}
            >
              {t("configureWeights")}
            </button>
          )}
          {weightsOpen && (
            <GradingWeights
              course={id!}
              version={data.version.id}
              components={data.components}
              onClose={() => setWeightsOpen(false)}
            />
          )}
        </section>
        <CourseSharing
          id={id!}
          teacher={String(data.course.teacher)}
          published={
            published && data.course.current_version === data.version.id
          }
        />
      </div>
      {editor && (
        <Modal
          title={t(editor.initial ? "edit" : "create")}
          onClose={() => setEditor(undefined)}
        >
          <RecordForm
            resource={editor.resource}
            initial={editor.initial}
            fixed={editor.fixed}
            defaults={editor.defaults}
            onDone={(row) => {
              if (
                row &&
                ["topics", "materials", "assignments", "tests"].includes(
                  editor.resource,
                )
              )
                setSelected({
                  type:
                    editor.resource === "topics" ? "topic" : editor.resource,
                  item: row as Activity,
                });
              setEditor(undefined);
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
              const result =
                confirm === "publish"
                  ? await action.run(`courses/${id}/publish/`, {
                      version: data.version.id,
                    })
                  : await action.run(confirm.slice(7), undefined, "DELETE");
              if (result.ok) {
                setConfirm(undefined);
                setSelected(undefined);
              }
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
    queryFn: ({ signal }) =>
      api<Row>(`chunks/${id}/`, "GET", undefined, signal),
  });
  if (query.isPending) return <Loading />;
  if (query.error)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  return query.data ? (
    <details>
      <summary>
        {t("source")} · {String(query.data.page_number)}
      </summary>
      <p>{String(query.data.content)}</p>
    </details>
  ) : null;
}
