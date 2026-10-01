import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { queryKeys } from "../../services/queryKeys";
import { useUser } from "../../app/Auth";
import { ErrorState, Loading } from "../../components/UI";
import type { Row } from "../../entities/types";

const domainFields: Record<string, string[]> = {
  users: [
    "first_name",
    "last_name",
    "email",
    "role",
    "owner_teacher",
    "is_active",
    "preferred_language",
  ],
  groups: ["name", "description", "teacher", "status"],
  disciplines: ["name", "code", "description", "status"],
  assignments: [
    "title",
    "description",
    "instructions",
    "deadline",
    "max_score",
    "allow_late_submission",
    "status",
  ],
  tests: [
    "title",
    "description",
    "time_limit_minutes",
    "max_attempts",
    "available_from",
    "available_until",
    "passing_score",
    "status",
  ],
  submissions: [
    "assignment_title",
    "student_name",
    "attempt_number",
    "submitted_at",
    "text_answer",
    "status",
    "score",
    "teacher_comment",
    "graded_at",
  ],
  notifications: ["title", "message", "created_at", "is_read"],
  content: ["title", "body", "language", "is_published"],
};
export function RecordDetails({
  row,
  resource = "",
}: {
  row: Row;
  resource?: string;
}) {
  const { t, i18n } = useTranslation();
  const fields = domainFields[resource];
  const entries: [string, unknown][] = fields
    ? fields.filter((key) => key in row).map((key) => [key, row[key]])
    : Object.entries(row).filter(([key]) => !["id", "file"].includes(key));
  const technical = ([key, value]: [string, unknown]) =>
    !fields &&
    (key.endsWith("_id") ||
      key === "request_id" ||
      (typeof value === "string" &&
        /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(value)));
  const render = (items: [string, unknown][]) => (
    <dl className="details">
      {items.map(([key, value]) => {
        let content;
        if (
          ["owner_teacher", "teacher"].includes(key) &&
          typeof value === "string"
        )
          content = <RelatedPerson id={value} />;
        else if (value == null || value === "") content = "—";
        else if (typeof value === "boolean") content = t(String(value));
        else if (
          (key.endsWith("_at") ||
            key === "deadline" ||
            key.startsWith("available_")) &&
          typeof value === "string" &&
          !Number.isNaN(Date.parse(value))
        )
          content = new Intl.DateTimeFormat(
            i18n.language === "kk" ? "kk-KZ" : "ru-RU",
            { dateStyle: "medium", timeStyle: "short" },
          ).format(new Date(value));
        else if (typeof value === "object")
          content = (
            <pre className="record-json">{JSON.stringify(value, null, 2)}</pre>
          );
        else content = t(String(value));
        return (
          <div key={key}>
            <dt>
              {t(
                key === "score" && resource === "submissions"
                  ? "ux.normalizedScore"
                  : key,
              )}
            </dt>
            <dd>{content}</dd>
          </div>
        );
      })}
    </dl>
  );
  return (
    <>
      {render(entries.filter((e) => !technical(e)))}
      {entries.some(technical) && (
        <details>
          <summary>{t("technicalDetails")}</summary>
          {render(entries.filter(technical))}
        </details>
      )}
    </>
  );
}

function RelatedPerson({ id }: { id: string }) {
  const user = useUser();
  const query = useQuery({
    queryKey: queryKeys.detail("users", id),
    queryFn: ({ signal }) => api<Row>(`users/${id}/`, "GET", undefined, signal),
    enabled: user.id !== id,
  });
  if (user.id === id)
    return <>{`${user.first_name} ${user.last_name}`.trim() || user.email}</>;
  if (query.isPending) return <Loading />;
  if (query.error)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  return (
    <>
      {`${query.data.first_name || ""} ${query.data.last_name || ""}`.trim() ||
        String(query.data.email)}
    </>
  );
}
