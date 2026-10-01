import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Download } from "lucide-react";
import { api } from "../../services/api";
import { ErrorState, Loading, Modal } from "../../components/UI";
import type { SourceDocument } from "../../entities/ai";
import type { Page } from "../../entities/types";

export function SourcePreview({
  source,
  onClose,
}: {
  source: SourceDocument;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [imageError, setImageError] = useState(false);
  const isImage = /\.(png|jpe?g)$/i.test(source.filename);
  const chunks = useQuery({
    queryKey: ["chunks", source.id, page],
    queryFn: () =>
      api<Page<{ id: string; page_number: number; content: string }>>(
        `sources/${source.id}/chunks/?page=${page}`,
      ),
    enabled: source.processing_status === "COMPLETED",
  });
  return (
    <Modal title={source.filename} onClose={onClose}>
      <div className="source-preview">
        <a className="button" href={`/api/v1/sources/${source.id}/download/`}>
          <Download size={16} />
          {t("sourcePreview.download")}
        </a>
        {isImage && !imageError && (
          <img
            className="source-preview-image"
            src={`/api/v1/sources/${source.id}/preview/`}
            alt={source.filename}
            onError={() => setImageError(true)}
          />
        )}
        {imageError && <p role="alert">{t("sourcePreview.imageError")}</p>}
        <h3>{t("sourcePreview.text")}</h3>
        <p className="muted">{t("sourcePreview.hint")}</p>
        {source.processing_status !== "COMPLETED" ? (
          <p>{t("sourcePreview.notReady")}</p>
        ) : chunks.isPending ? (
          <Loading />
        ) : chunks.isError ? (
          <ErrorState
            error={chunks.error}
            retry={() => void chunks.refetch()}
          />
        ) : (
          <>
            {!chunks.data.results.length && <p>{t("sourcePreview.empty")}</p>}
            {chunks.data.results.map((chunk) => (
              <section className="source-preview-chunk" key={chunk.id}>
                <strong>
                  {t("sourcePreview.page", { number: chunk.page_number })}
                </strong>
                <p>{chunk.content}</p>
              </section>
            ))}
            {(chunks.data.previous || chunks.data.next) && (
              <nav className="pagination" aria-label={t("sourcePreview.text")}>
                <button
                  disabled={!chunks.data.previous}
                  onClick={() => setPage((p) => p - 1)}
                >
                  {t("previous")}
                </button>
                <span>{page}</span>
                <button
                  disabled={!chunks.data.next}
                  onClick={() => setPage((p) => p + 1)}
                >
                  {t("next")}
                </button>
              </nav>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}
