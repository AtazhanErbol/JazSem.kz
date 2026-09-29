import { useTranslation } from "react-i18next";
import type { Row } from "../../entities/types";

export function RecordDetails({ row }: { row: Row }) {
  const { t, i18n } = useTranslation();
  const entries = Object.entries(row).filter(
    ([key]) => !["id", "file"].includes(key),
  );
  const technical = ([key, value]: [string, unknown]) =>
    key.endsWith("_id") ||
    key === "request_id" ||
    (typeof value === "string" &&
      /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(value));
  const render = (items: [string, unknown][]) => (
    <dl className="details">
      {items.map(([key, value]) => {
        let content;
        if (value == null || value === "") content = "—";
        else if (typeof value === "boolean") content = t(String(value));
        else if (
          (key.endsWith("_at") || key === "deadline") &&
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
            <dt>{t(key)}</dt>
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
