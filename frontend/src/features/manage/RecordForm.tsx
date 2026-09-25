import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { allRows } from "../../services/api";
import type { Row } from "../../entities/types";
import { useUser } from "../../app/Auth";
import { useAction } from "../../hooks/useAction";
import { fields, type Field } from "./fields";

export function RecordForm({
  resource,
  initial,
  fixed = {},
  onDone,
}: {
  resource: string;
  initial?: Row;
  fixed?: Record<string, unknown>;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const user = useUser();
  const action = useAction();
  const activeFields = (fields[resource] || []).filter(
    (f) =>
      !(f.name in fixed) && !(f.name === "teacher" && user.role === "TEACHER"),
  );
  const shape: Record<string, z.ZodType> = {};
  const defaults: Record<string, unknown> = {};
  for (const field of activeFields) {
    shape[field.name] =
      field.type === "checkbox"
        ? z.boolean()
        : field.type === "file"
          ? z.unknown()
          : field.type === "number"
            ? z.coerce.number().min(0)
            : field.required
              ? z.string().min(1)
              : z.string();
    defaults[field.name] =
      initial?.[field.name] ??
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
    if (field.name === "teachers" && Array.isArray(defaults[field.name]))
      defaults[field.name] = (defaults[field.name] as string[])[0] || "";
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
      if (field.name === "teachers") payload.teachers = [payload.teachers];
    }
    let body: unknown = payload;
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
    if (result) onDone();
  }
  return (
    <form className="record-form" onSubmit={form.handleSubmit(submit)}>
      {activeFields.map((field) => (
        <label
          key={field.name}
          className={field.type === "checkbox" ? "check-label" : ""}
        >
          {t(field.name)}
          {field.source ? (
            <SourceSelect
              field={field}
              registration={form.register(field.name)}
            />
          ) : field.type === "select" ? (
            <select {...form.register(field.name)}>
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
        <button type="button" onClick={onDone}>
          {t("cancel")}
        </button>
        <button className="primary" disabled={action.pending}>
          {t("save")}
        </button>
      </div>
    </form>
  );
}
function SourceSelect({
  field,
  registration,
}: {
  field: Field;
  registration: ReturnType<ReturnType<typeof useForm>["register"]>;
}) {
  const query = useQuery({
    queryKey: ["options", field.source],
    queryFn: () => allRows(field.source!),
  });
  const { t } = useTranslation();
  return (
    <select {...registration}>
      <option value="">{t("noSelection")}</option>
      {query.data?.map((row) => (
        <option key={row.id} value={row.id}>
          {String(row.title || row.name || row.email || row.id)}
        </option>
      ))}
    </select>
  );
}
