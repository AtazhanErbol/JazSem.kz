import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Plus, Search, ArrowUpRight } from "lucide-react";
import type { Page, Row } from "../../entities/types";
import { api } from "../../services/api";
import { Badge, Empty, ErrorState, Loading, Modal } from "../../components/UI";
import { useUser } from "../../app/Auth";
import { useAction } from "../../hooks/useAction";
import { RecordForm } from "./RecordForm";
import { fields } from "./fields";

export function ResourcePage({ resource }: { resource: string }) {
  const { t } = useTranslation();
  const user = useUser();
  const action = useAction();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [edit, setEdit] = useState<Row | null | undefined>();
  const [confirm, setConfirm] = useState<{ path: string; body?: unknown }>();
  const [detail, setDetail] = useState<Row>();
  const query = useQuery({
    queryKey: [resource, page, search],
    queryFn: () =>
      api<Page<Row>>(
        `${resource}/?page=${page}&search=${encodeURIComponent(search)}`,
      ),
  });
  const canCreate =
    user.role !== "STUDENT" &&
    Boolean(fields[resource]) &&
    ["users", "courses", "groups", "disciplines", "content"].includes(
      resource,
    ) &&
    ((resource !== "disciplines" && resource !== "content") ||
      user.role === "ADMIN");
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
          <h1>{t(title)}</h1>
          <p className="muted">
            {query.data?.count ?? "—"} {t("all").toLowerCase()}
          </p>
        </div>
        {canCreate && (
          <button className="primary" onClick={() => setEdit(null)}>
            <Plus size={18} />
            {t("create")}
          </button>
        )}
      </div>
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
      {action.feedback}
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : !query.data.results.length ? (
        <Empty>
          {canCreate && (
            <button onClick={() => setEdit(null)}>{t("create")}</button>
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
                      {new Date(String(row.created_at)).toLocaleDateString()}
                    </small>
                  )}
                </div>
                <div className="row-actions">
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
                  {canCreate && (
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
      {edit !== undefined && (
        <Modal
          title={t(edit ? "edit" : "create")}
          onClose={() => setEdit(undefined)}
        >
          <RecordForm
            resource={resource}
            initial={edit || undefined}
            onDone={() => setEdit(undefined)}
          />
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
          <dl className="details">
            {Object.entries(detail)
              .filter(([key]) => !["id", "file"].includes(key))
              .map(([key, value]) => (
                <div key={key}>
                  <dt>{t(key)}</dt>
                  <dd>
                    {typeof value === "object"
                      ? JSON.stringify(value)
                      : String(value ?? "—")}
                  </dd>
                </div>
              ))}
          </dl>
        </Modal>
      )}
    </>
  );
}
