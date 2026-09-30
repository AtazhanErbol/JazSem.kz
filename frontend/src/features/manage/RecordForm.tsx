import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { allRows, ApiError } from "../../services/api";
import { ErrorState, Loading } from "../../components/UI";
import type { Row } from "../../entities/types";
import { useUser } from "../../app/Auth";
import { useAction } from "../../hooks/useAction";
import { fields, type Field } from "./fields";

export function RecordForm({
  resource,
  initial,
  fixed = {},
  defaults: suppliedDefaults = {},
  onDone,
  submitLabel,
}: {
  resource: string;
  initial?: Row;
  fixed?: Record<string, unknown>;
  defaults?: Record<string, unknown>;
  onDone: (row?: Row) => void;
  submitLabel?: string;
}) {
  const { t } = useTranslation();
  const user = useUser();
  const action = useAction();
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
        ? z.array(z.string()).min(1)
        : field.type === "checkbox"
          ? z.boolean()
          : field.type === "file"
            ? z.unknown()
            : field.type === "number"
              ? z.coerce
                  .number()
                  .min(field.min ?? 0)
                  .max(field.max ?? Number.MAX_SAFE_INTEGER)
              : field.required
                ? z.string().min(1)
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
  async function submit(data: Record<string, unknown>) {
    const payload: Record<string, unknown> = {
      ...data,
      ...fixed,
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
      `${resource}/${initial ? initial.id + "/" : ""}`,
      body,
      initial ? "PATCH" : "POST",
    );
    if (result.ok) onDone(result.data);
    else if (result.error instanceof ApiError)
      for (const [name, message] of Object.entries(result.error.fieldErrors))
        form.setError(name, { type: "server", message });
  }
  return (
    <form className="record-form" onSubmit={form.handleSubmit(submit)}>
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
        .map((field) => (
          <label
            key={field.name}
            className={field.type === "checkbox" ? "check-label" : ""}
          >
            {t(field.name)}
            {field.source ? (
              <SourceSelect
                field={field}
                value={form.watch(field.name) as string | string[]}
                registration={form.register(field.name)}
              />
            ) : field.type === "select" ? (
              <select aria-label={t(field.name)} {...form.register(field.name)}>
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
            ) : field.type === "textarea" ? (
              <textarea rows={5} {...form.register(field.name)} />
            ) : (
              <input
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
              <small className="field-error">
                {String(form.formState.errors[field.name]?.message)}
              </small>
            )}
          </label>
        ))}
      {action.feedback}
      <div className="form-actions">
        <button type="button" onClick={() => onDone()}>
          {t("cancel")}
        </button>
        <button
          className="primary"
          disabled={action.pending || form.formState.isSubmitting}
        >
          {submitLabel || t("save")}
        </button>
      </div>
    </form>
  );
}
function SourceSelect({
  field,
  registration,
  value,
}: {
  field: Field;
  value: string | string[];
  registration: ReturnType<ReturnType<typeof useForm>["register"]>;
}) {
  const query = useQuery({
    queryKey: ["options", field.source],
    queryFn: () => allRows(field.source!),
  });
  const { t } = useTranslation();
  if (query.isPending) return <Loading />;
  if (query.error)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  return (
    <select
      multiple={field.name === "teachers"}
      value={value}
      aria-label={t(field.name)}
      {...registration}
    >
      {field.name !== "teachers" && (
        <option value="">
          {t(
            field.name === "owner_teacher"
              ? "workspace.unassigned"
              : "noSelection",
          )}
        </option>
      )}
      {query.data?.map((row) => (
        <option key={row.id} value={row.id}>
          {String(
            row.title ||
              row.name ||
              (row.first_name
                ? `${row.first_name} ${row.last_name || ""} · ${row.email}`
                : row.email) ||
              row.id,
          )}
        </option>
      ))}
    </select>
  );
}
