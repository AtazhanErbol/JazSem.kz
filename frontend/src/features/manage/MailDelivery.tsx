import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ErrorState, Loading } from "../../components/UI";
import { Pagination } from "../../components/Pagination";
import type { Page } from "../../entities/types";
import { api } from "../../services/api";
import { useAction } from "../../hooks/useAction";

interface Delivery {
  id: string;
  recipient: string;
  status: "PENDING" | "SENDING" | "RETRY" | "SENT" | "FAILED";
  attempts: number;
  created_at: string;
  next_retry_at: string | null;
  error_code: string;
}

export function MailDelivery() {
  const { t, i18n } = useTranslation();
  const [params, setParams] = useSearchParams();
  const status = params.get("status") || "";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const action = useAction();
  const query = useQuery({
    queryKey: ["mail-outbox", status, page],
    queryFn: () =>
      api<Page<Delivery>>(
        `mail-outbox/?page=${page}${status ? `&status=${encodeURIComponent(status)}` : ""}`,
      ),
  });
  const metrics = useQuery({
    queryKey: ["mail-metrics"],
    queryFn: () =>
      api<{ counts: Record<string, number>; oldest_unsent_seconds: number }>(
        "mail-outbox/metrics/",
      ),
  });
  const date = (value: string) =>
    new Date(value).toLocaleString(i18n.language === "kk" ? "kk-KZ" : "ru-RU");
  return (
    <>
      <h1>{t("mail.title")}</h1>
      <p className="muted">{t("mail.hint")}</p>
      <section
        className="panel mail-status-guide"
        aria-labelledby="mail-status-guide-title"
      >
        <h2 id="mail-status-guide-title">{t("mail.guideTitle")}</h2>
        <p className="muted">{t("mail.guideFlow")}</p>
        <dl>
          {["PENDING", "SENDING", "RETRY", "FAILED", "SENT"].map((value) => (
            <div key={value}>
              <dt>{t(`mail.${value}`)}</dt>
              <dd>{t(`mail.descriptions.${value}`)}</dd>
            </div>
          ))}
        </dl>
      </section>
      {metrics.isError && (
        <ErrorState
          error={metrics.error}
          retry={() => void metrics.refetch()}
        />
      )}
      {metrics.data && (
        <p role="status">
          {t("mail.queueAge", {
            minutes: Math.ceil(metrics.data.oldest_unsent_seconds / 60),
            failed: metrics.data.counts.FAILED || 0,
          })}
        </p>
      )}
      <div className="filter-toolbar">
        <label>
          {t("status")}
          <select
            value={status}
            onChange={(event) =>
              setParams(
                event.target.value
                  ? { status: event.target.value, page: "1" }
                  : { page: "1" },
              )
            }
          >
            <option value="">{t("all")}</option>
            {["FAILED", "RETRY", "PENDING", "SENDING", "SENT"].map((value) => (
              <option key={value} value={value}>
                {t(`mail.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <button
          onClick={() => {
            void query.refetch();
            void metrics.refetch();
          }}
        >
          {t("mail.refresh")}
        </button>
      </div>
      {action.feedback}
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : (
        <>
          {!query.data.results.length && (
            <p className="panel">
              {t(status ? "mail.empty" : "mail.emptyAll")}
            </p>
          )}
          {query.data.results.map((delivery) => (
            <article className="panel" key={delivery.id}>
              <h2>{delivery.recipient}</h2>
              <p>
                {t(`mail.${delivery.status}`)} · {date(delivery.created_at)}
              </p>
              <p>{t("mail.attempts", { count: delivery.attempts })}</p>
              {delivery.error_code && (
                <p role="status">
                  {t(`mail.errors.${delivery.error_code}`, {
                    defaultValue: t("mail.errors.DELIVERY_FAILED"),
                  })}
                </p>
              )}
              {delivery.next_retry_at && (
                <p>
                  {t("mail.next")}: {date(delivery.next_retry_at)}
                </p>
              )}
              {["FAILED", "RETRY"].includes(delivery.status) && (
                <button
                  disabled={action.pending}
                  onClick={() =>
                    void action.run(`mail-outbox/${delivery.id}/retry/`)
                  }
                >
                  {t("mail.retry")}
                </button>
              )}
            </article>
          ))}
          <Pagination
            page={page}
            count={query.data.count}
            onChange={(nextPage) =>
              setParams(
                status
                  ? { status, page: String(nextPage) }
                  : { page: String(nextPage) },
              )
            }
          />
        </>
      )}
    </>
  );
}
