import { useState } from "react";
import { useTranslation } from "react-i18next";
import { RemoteSelect } from "../../components/RemoteSelect";
import { useUser } from "../../app/Auth";
import { capabilities } from "./capabilities";

export function ResourceFilters({
  resource,
  params,
  change,
}: {
  resource: string;
  params: URLSearchParams;
  change: (key: string, value: string) => void;
}) {
  const { t } = useTranslation();
  const user = useUser();
  const filters = (capabilities[resource]?.filters || []).filter(
    (filter) =>
      (!filter.adminOnly || user.role === "ADMIN") &&
      (!filter.authorOnly || user.role !== "STUDENT"),
  );
  const [open, setOpen] = useState(() =>
    filters.some((filter) => params.has(filter.key)),
  );
  const orders = capabilities[resource]?.order || [];
  if (!filters.length && !orders.length) return null;
  return (
    <details
      className="resource-filters"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>{t("ux.filter")}</summary>
      {open && (
        <div className="filters-grid">
          {orders.length > 0 && (
            <label>
              {t("ux.orderBy")}
              <select
                aria-label={t("ux.orderBy")}
                value={params.get("ordering") || orders[0]}
                onChange={(event) => change("ordering", event.target.value)}
              >
                {orders.map((order) => (
                  <option key={order} value={order}>
                    {t(`ux.orderLabels.${order}`)}
                  </option>
                ))}
              </select>
            </label>
          )}
          {filters.map((filter) => (
            <div key={filter.key}>
              <strong>{t(filter.label)}</strong>
              {filter.source ? (
                <RemoteSelect
                  source={filter.source}
                  label={t(filter.label)}
                  value={params.get(filter.key) || ""}
                  emptyLabel={t("all")}
                  onChange={(value) => change(filter.key, String(value))}
                />
              ) : (
                <select
                  aria-label={t(filter.label)}
                  value={params.get(filter.key) || ""}
                  onChange={(event) => change(filter.key, event.target.value)}
                >
                  <option value="">{t("all")}</option>
                  {filter.values?.map((value) => (
                    <option key={value} value={value}>
                      {t(
                        filter.key === "due"
                          ? value === "none"
                            ? "ux.noDeadline"
                            : `ux.${value}`
                          : value,
                      )}
                    </option>
                  ))}
                </select>
              )}
            </div>
          ))}
        </div>
      )}
    </details>
  );
}
