import { useEffect, useId, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api, ApiError } from "../../services/api";
import { RemoteSelect } from "../../components/RemoteSelect";
import { useUnsavedChanges } from "../../hooks/useUnsavedChanges";
import type { Page, Row } from "../../entities/types";
import { ErrorState, Loading } from "../../components/UI";
import { useUser } from "../../app/Auth";
import { useAction } from "../../hooks/useAction";
import { fields } from "./fields";
import { Attachments, type AttachmentOwner } from "../authoring/Attachments";
import { ContentEditor, LearningContent } from "../authoring/LearningContent";
import { LectureAssistant } from "../authoring/LectureAssistant";

export function RecordForm({
  resource,
  initial,
  fixed = {},
  defaults: suppliedDefaults = {},
  onDone,
  submitLabel,
  course,
  onRelatedEdit,
}: {
  resource: string;
  initial?: Row;
  fixed?: Record<string, unknown>;
  defaults?: Record<string, unknown>;
  onDone: (row?: Row) => void;
  submitLabel?: string;
  course?: string;
  onRelatedEdit?: (
    resource: string,
    initial?: Row,
    fixed?: Record<string, unknown>,
  ) => void;
}) {
  const { t } = useTranslation();
  const user = useUser();
  const action = useAction();
  const formId = useId();
  const [savedRow, setSavedRow] = useState<Row>();
  const current = savedRow || initial;
  const [section, setSection] = useState("main");
  const [attachmentBusy, setAttachmentBusy] = useState(false),
    [attachmentDirty, setAttachmentDirty] = useState(false);
  const [aiDirty, setAIDirty] = useState(false),
    [selectedSection, setSelectedSection] = useState(0);
  const [previousContent, setPreviousContent] = useState<string[]>([]);
  const owners: Record<string, AttachmentOwner> = {
    topics: "topic",
    assignments: "assignment",
    tests: "test",
    questions: "question",
  };
  const owner = owners[resource],
    learning = !!owner;
  const sections = learning
    ? [
        "main",
        ...(resource === "topics" || resource === "assignments"
          ? ["content"]
          : []),
        ...(resource === "assignments" ? ["videos"] : []),
        ...(resource === "tests" ? ["questions"] : []),
        "materials",
        ...(resource === "topics" ? ["ai"] : ["settings"]),
        "preview",
      ]
    : [];
  const fieldSection = (name: string) =>
    name === "title" || name === "text" || name === "type"
      ? "main"
      : name === "content" || name === "instructions" || name === "description"
        ? resource === "tests"
          ? "main"
          : "content"
        : resource === "topics"
          ? "main"
          : "settings";
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const accessibility = (name: string) => ({
    "aria-invalid": !!form.formState.errors[name],
    "aria-describedby": form.formState.errors[name]
      ? `${formId}-${name}-error`
      : undefined,
  });
  const activeFields = (fields[resource] || []).filter(
    (f) =>
      !(f.name in fixed) &&
      !(
        ["teacher", "owner_teacher"].includes(f.name) && user.role === "TEACHER"
      ) &&
      !(f.name === "role" && initial),
  );
  const shape: Record<string, z.ZodType> = {};
  const defaults: Record<string, unknown> = {};
  for (const field of activeFields) {
    shape[field.name] =
      field.name === "teachers"
        ? z.array(z.string()).min(1, t("ux.required"))
        : field.type === "checkbox"
          ? z.boolean()
          : field.type === "file"
            ? z.unknown()
            : field.type === "number"
              ? z.coerce
                  .number({ error: t("ux.invalidNumber") })
                  .min(
                    field.min ?? 0,
                    t("ux.minValue", { value: field.min ?? 0 }),
                  )
                  .max(
                    field.max ?? Number.MAX_SAFE_INTEGER,
                    t("ux.maxValue", {
                      value: field.max ?? Number.MAX_SAFE_INTEGER,
                    }),
                  )
              : field.required
                ? z.string().trim().min(1, t("ux.required"))
                : z.string();
    defaults[field.name] =
      initial?.[field.name] ??
      suppliedDefaults[field.name] ??
      field.default ??
      (field.type === "checkbox" ? false : "");
    if (field.type === "datetime-local" && defaults[field.name])
      defaults[field.name] = new Date(
        new Date(String(defaults[field.name])).getTime() -
          new Date(String(defaults[field.name])).getTimezoneOffset() * 60000,
      )
        .toISOString()
        .slice(0, 16);
    if (field.type === "file") defaults[field.name] = undefined;
    if (field.name === "teachers" && !Array.isArray(defaults[field.name]))
      defaults[field.name] = [];
  }
  const form = useForm<Record<string, unknown>>({
    resolver: zodResolver(z.object(shape)),
    defaultValues: defaults,
  });
  const dirty = form.formState.isDirty || attachmentDirty || aiDirty;
  const allowNavigation = useUnsavedChanges(dirty || attachmentBusy);
  const invalid = (errors: Record<string, unknown>) => {
    const name = Object.keys(errors)[0];
    if (learning && name) {
      setSection(fieldSection(name));
      requestAnimationFrame(() => form.setFocus(name));
    }
  };
  async function submit(
    data: Record<string, unknown>,
    continueEditing = false,
  ) {
    if (attachmentBusy || attachmentDirty || aiDirty) return;
    const payload: Record<string, unknown> = {
      ...data,
      ...fixed,
      ...(resource === "topics" && current?.updated_at
        ? { expected_updated_at: current.updated_at }
        : {}),
      ...(user.role === "TEACHER" && ["courses", "groups"].includes(resource)
        ? { teacher: user.id }
        : {}),
    };
    for (const field of activeFields) {
      if (field.type === "datetime-local")
        payload[field.name] = payload[field.name]
          ? new Date(String(payload[field.name])).toISOString()
          : null;
    }
    let body: unknown = payload;
    if (resource === "users") {
      if ((initial?.role || payload.role) !== "STUDENT")
        delete payload.owner_teacher;
      else if (user.role === "ADMIN")
        payload.owner_teacher = payload.owner_teacher || null;
    }
    const upload = payload.file as FileList | undefined;
    if (upload?.length) {
      const fd = new FormData();
      for (const [key, value] of Object.entries(payload))
        if (key !== "file" && value !== null) fd.append(key, String(value));
      fd.append("file", upload[0]);
      body = fd;
    } else delete payload.file;
    const result = await action.run<Row>(
      `${resource}/${current ? current.id + "/" : ""}`,
      body,
      current ? "PATCH" : "POST",
    );
    if (!mounted.current) return;
    if (result.ok) {
      form.reset(data);
      if (continueEditing) {
        setSavedRow(result.data);
        return;
      }
      allowNavigation();
      onDone(result.data);
    } else if (result.error instanceof ApiError)
      for (const [name, message] of Object.entries(result.error.fieldErrors))
        form.setError(name, { type: "server", message }, { shouldFocus: true });
  }
  return (
    <form
      data-dirty={dirty}
      data-pending={action.pending || attachmentBusy}
      onReset={() => {
        form.reset();
        allowNavigation();
      }}
      className={`record-form${learning ? " learning-record" : ""}`}
      onSubmit={form.handleSubmit((data) => submit(data), invalid)}
    >
      {learning && (
        <>
          <div className="authoring-header">
            <span
              className={`badge${form.formState.isDirty ? " changed" : ""}`}
            >
              {t(
                form.formState.isDirty
                  ? "authoring.changed"
                  : "authoring.draft",
              )}
            </span>
            <small>{t("authoring.publication")}</small>
          </div>
          <nav className="authoring-sections" aria-label={t("edit")}>
            {sections.map((name) => (
              <button
                key={name}
                type="button"
                aria-current={section === name ? "step" : undefined}
                disabled={attachmentBusy || action.pending}
                onClick={() => {
                  if (
                    (attachmentDirty || aiDirty) &&
                    !window.confirm(t("ux.unsavedConfirm"))
                  )
                    return;
                  setSection(name);
                }}
              >
                {t(`authoring.${name}`)}
              </button>
            ))}
          </nav>
          <h3 className="authoring-section-title">
            {t(`authoring.${section}`)}
          </h3>
        </>
      )}
      {resource === "users" && initial && (
        <p>
          {t("role")}: <strong>{t(String(initial.role))}</strong>
        </p>
      )}
      {activeFields
        .filter(
          (field) =>
            field.name !== "owner_teacher" ||
            (initial?.role || form.watch("role")) === "STUDENT",
        )
        .filter((field) => !learning || fieldSection(field.name) === section)
        .map((field) => {
          const FieldTag =
            field.type === "textarea" &&
            learning &&
            ["content", "instructions", "description"].includes(field.name)
              ? "div"
              : "label";
          return (
            <FieldTag
              key={field.name}
              className={field.type === "checkbox" ? "check-label" : ""}
            >
              {t(field.name)}
              {field.source ? (
                <RemoteSelect
                  {...accessibility(field.name)}
                  source={field.source}
                  label={t(field.name)}
                  multiple={field.name === "teachers"}
                  value={form.watch(field.name) as string | string[]}
                  emptyLabel={
                    field.name === "owner_teacher"
                      ? t("workspace.unassigned")
                      : undefined
                  }
                  onChange={(value) =>
                    form.setValue(field.name, value, {
                      shouldDirty: true,
                      shouldValidate: true,
                    })
                  }
                />
              ) : field.type === "select" ? (
                <select
                  {...accessibility(field.name)}
                  aria-label={t(field.name)}
                  {...form.register(field.name)}
                >
                  {field.options
                    ?.filter(
                      (o) =>
                        field.name !== "role" ||
                        user.role === "ADMIN" ||
                        o === "STUDENT",
                    )
                    .map((o) => (
                      <option key={o} value={o}>
                        {t(o)}
                      </option>
                    ))}
                </select>
              ) : field.type === "textarea" &&
                learning &&
                ["content", "instructions", "description"].includes(
                  field.name,
                ) ? (
                <ContentEditor
                  value={String(form.watch(field.name) || "")}
                  onChange={(value) =>
                    form.setValue(field.name, value, {
                      shouldDirty: true,
                      shouldValidate: true,
                    })
                  }
                  label={t(field.name)}
                  invalid={!!form.formState.errors[field.name]}
                  onSelectSection={setSelectedSection}
                />
              ) : field.type === "textarea" ? (
                <textarea
                  {...accessibility(field.name)}
                  rows={5}
                  {...form.register(field.name)}
                />
              ) : (
                <input
                  {...accessibility(field.name)}
                  type={field.type || "text"}
                  min={field.min}
                  max={field.max}
                  {...form.register(field.name)}
                  accept={
                    field.type === "file"
                      ? ".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg"
                      : undefined
                  }
                />
              )}{" "}
              {form.formState.errors[field.name] && (
                <small
                  id={`${formId}-${field.name}-error`}
                  className="field-error"
                  role="alert"
                >
                  {String(form.formState.errors[field.name]?.message)}
                </small>
              )}
            </FieldTag>
          );
        })}
      {learning &&
        ["materials", "videos", "ai"].includes(section) &&
        !current && (
          <div className="notice">
            <p>{t("authoring.saveFirst")}</p>
            <button
              type="button"
              className="primary"
              disabled={action.pending}
              onClick={() =>
                void form.handleSubmit((data) => submit(data, true), invalid)()
              }
            >
              {t("authoring.saveFirstAction")}
            </button>
          </div>
        )}
      {learning && current && ["materials", "videos"].includes(section) && (
        <Attachments
          key={`${section}-${current.id}`}
          owner={owner}
          ownerId={current.id}
          mode={section === "videos" ? "videos" : "files"}
          editable
          onBusyChange={setAttachmentBusy}
          onDirtyChange={setAttachmentDirty}
          heading={false}
        />
      )}
      {resource === "topics" && section === "ai" && current && (
        <LectureAssistant
          topic={current.id}
          title={String(form.watch("title") || "")}
          content={String(form.watch("content") || "")}
          course={course}
          selectedSection={selectedSection}
          onSelectSection={setSelectedSection}
          onDirtyChange={setAIDirty}
          onUse={(draft) => {
            const content = String(form.getValues("content") || "");
            if (
              content.trim() &&
              !window.confirm(t("authoring.replaceTextConfirm"))
            )
              return;
            setPreviousContent((old) => [...old, content]);
            form.setValue("content", draft.content, {
              shouldDirty: true,
              shouldValidate: true,
            });
            setSection("content");
          }}
        />
      )}
      {resource === "topics" &&
        previousContent.length > 0 &&
        section === "content" && (
          <button
            type="button"
            onClick={() => {
              form.setValue(
                "content",
                previousContent[previousContent.length - 1],
                { shouldDirty: true },
              );
              setPreviousContent((old) => old.slice(0, -1));
            }}
          >
            {t("authoring.undo")}
          </button>
        )}
      {learning && section === "questions" && (
        <>
          <p className="notice">{t("authoring.questionsHint")}</p>
          {current && (
            <QuestionsList
              test={current.id}
              edit={
                onRelatedEdit
                  ? (resource, row, fixed) => {
                      if (dirty && !window.confirm(t("ux.unsavedConfirm")))
                        return;
                      onRelatedEdit(resource, row, fixed);
                    }
                  : undefined
              }
            />
          )}
        </>
      )}
      {learning && section === "preview" && (
        <section className="student-preview">
          <h2>{String(form.watch("title") || form.watch("text") || "")}</h2>
          <LearningContent
            content={String(
              form.watch("content") ||
                form.watch("instructions") ||
                form.watch("description") ||
                "",
            )}
          />
          {current && (
            <>
              {resource === "assignments" && (
                <Attachments owner={owner} ownerId={current.id} mode="videos" />
              )}
              <Attachments owner={owner} ownerId={current.id} />
            </>
          )}
          {resource === "tests" && current && (
            <QuestionsList test={current.id} />
          )}
        </section>
      )}
      {action.feedback}
      <div className="form-actions">
        <button
          type="button"
          disabled={action.pending || attachmentBusy}
          onClick={() => {
            if (!dirty || window.confirm(t("ux.unsavedConfirm"))) {
              allowNavigation();
              onDone(savedRow);
            }
          }}
        >
          {t("cancel")}
        </button>
        <button
          className="primary"
          disabled={
            action.pending ||
            form.formState.isSubmitting ||
            attachmentBusy ||
            attachmentDirty ||
            aiDirty ||
            (learning &&
              !["main", "content", "settings", "preview"].includes(section))
          }
        >
          {submitLabel || t("save")}
        </button>
      </div>
    </form>
  );
}

function QuestionsList({
  test,
  edit,
}: {
  test: string;
  edit?: (resource: string, row?: Row, fixed?: Record<string, unknown>) => void;
}) {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: ["questions", "authoring", test],
    queryFn: () => api<Page<Row>>(`questions/?test=${test}&ordering=order`),
  });
  return (
    <section className="authoring-questions">
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} />
      ) : (
        query.data?.results.map((question, index) => (
          <article key={question.id}>
            <strong>
              {index + 1}. {String(question.text)}
            </strong>
            {edit && (
              <button
                type="button"
                onClick={() => edit("questions", question, { test })}
              >
                {t("edit")}
              </button>
            )}
            {Array.isArray(question.options) && (
              <ul>
                {(question.options as Row[]).map((option) => (
                  <li key={option.id}>
                    {String(option.text)}
                    {edit && (
                      <button
                        type="button"
                        onClick={() =>
                          edit("options", option, { question: question.id })
                        }
                      >
                        {t("edit")}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {edit && (
              <button
                type="button"
                onClick={() =>
                  edit("options", undefined, { question: question.id })
                }
              >
                {t("authoring.addAnswer")}
              </button>
            )}
            <Attachments owner="question" ownerId={question.id} />
          </article>
        ))
      )}
      {edit && (
        <button
          type="button"
          onClick={() => edit("questions", undefined, { test })}
        >
          + {t("addQuestion")}
        </button>
      )}
    </section>
  );
}
