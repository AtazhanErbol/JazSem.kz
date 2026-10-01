import { useEffect, useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { Page, Row } from "../entities/types";
import { api } from "../services/api";
import { queryKeys } from "../services/queryKeys";
import { ErrorState, Loading } from "./UI";
import { Pagination } from "./Pagination";

export function optionLabel(row: Row) {
  return String(
    row.title ||
      row.name ||
      (row.first_name
        ? `${row.first_name} ${row.last_name || ""} · ${row.email || ""}`
        : row.email) ||
      "—",
  );
}
export function RemoteSelect({
  source,
  label,
  value,
  onChange,
  multiple = false,
  emptyLabel,
  ...accessibility
}: {
  source: string;
  label: string;
  value: string | string[];
  onChange: (value: string | string[]) => void;
  multiple?: boolean;
  emptyLabel?: string;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
}) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search), 250);
    return () => clearTimeout(timer);
  }, [search]);
  const url = new URL(source, "http://local.invalid/");
  url.searchParams.set("search", debounced);
  url.searchParams.set("page", String(page));
  const query = useQuery({
    queryKey: queryKeys.options(source, debounced, page),
    queryFn: ({ signal }) =>
      api<Page<Row>>(
        url.pathname.slice(1) + url.search,
        "GET",
        undefined,
        signal,
      ),
  });
  const ids = Array.isArray(value) ? value : value ? [value] : [];
  const missing = ids.filter(
    (id) => !query.data?.results.some((row) => row.id === id),
  );
  const selected = useQueries({
    queries: missing.map((id) => ({
      queryKey: queryKeys.detail(source.split("/")[0], id),
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        api<Row>(`${source.split("/")[0]}/${id}/`, "GET", undefined, signal),
      staleTime: 60000,
    })),
  });
  const choices = [
    ...selected.flatMap((q) => (q.data ? [q.data] : [])),
    ...(query.data?.results || []),
  ];
  return (
    <div className="remote-select">
      <input
        type="search"
        aria-label={`${t("search")}: ${label}`}
        placeholder={t("search")}
        value={search}
        onChange={(event) => {
          setSearch(event.target.value);
          setPage(1);
        }}
      />
      {query.isPending && <Loading />}
      {query.error && (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      )}
      {selected.some((q) => q.error) && (
        <p role="alert">{t("ux.selectedUnavailable")}</p>
      )}
      <select
        {...accessibility}
        aria-busy={query.isPending || selected.some((q) => q.isPending)}
        disabled={query.isPending || selected.some((q) => q.isPending)}
        aria-label={label}
        multiple={multiple}
        value={value}
        onChange={(event) =>
          onChange(
            multiple
              ? Array.from(
                  event.target.selectedOptions,
                  (option) => option.value,
                )
              : event.target.value,
          )
        }
      >
        {!multiple && (
          <option value="">{emptyLabel || t("noSelection")}</option>
        )}
        {choices.map((row) => (
          <option key={row.id} value={row.id}>
            {optionLabel(row)}
          </option>
        ))}
      </select>
      {query.data && !query.data.count && <small>{t("ux.noMatches")}</small>}
      {query.data && (
        <Pagination page={page} count={query.data.count} onChange={setPage} />
      )}
    </div>
  );
}
