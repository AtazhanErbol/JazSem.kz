import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Download, Upload } from "lucide-react";
import { api } from "../../services/api";
import { useAction } from "../../hooks/useAction";
import { Modal, ErrorState } from "../../components/UI";
type Preview = {
  token: string;
  existing: number;
  questions: {
    text: string;
    options: string[];
    correct: string[];
    score: number;
  }[];
};
export function TestImport({ id }: { id: string }) {
  const { t } = useTranslation();
  const action = useAction();
  const [preview, setPreview] = useState<Preview>();
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  return (
    <div className="test-import">
      <p>{t("importHint")}</p>
      <div className="row-actions">
        <a className="button" href={`/api/v1/tests/${id}/import-template/`}>
          <Download size={16} />
          {t("importTemplate")}
        </a>
        <label className="button import-file">
          <Upload size={16} />
          {t("importFile")}
          <input
            aria-label={t("importFile")}
            type="file"
            accept=".xlsx"
            disabled={busy || action.pending}
            onChange={async (e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (!file) return;
              setError(undefined);
              setPreview(undefined);
              setBusy(true);
              try {
                const form = new FormData();
                form.append("file", file);
                setPreview(
                  await api<Preview>(
                    `tests/${id}/import-preview/`,
                    "POST",
                    form,
                  ),
                );
              } catch (err) {
                setError(err);
              } finally {
                setBusy(false);
              }
            }}
          />
        </label>
      </div>
      {busy && <p role="status">{t("importChecking")}</p>}
      {error != null && <ErrorState error={error} />}
      {action.feedback}
      {preview && (
        <Modal
          title={t("importPreview")}
          onClose={() => {
            if (!action.pending) setPreview(undefined);
          }}
        >
          <p>
            {t("importSummary", {
              count: preview.questions.length,
              existing: preview.existing,
            })}
          </p>
          <ol className="import-preview">
            {preview.questions.map((q, i) => (
              <li key={i}>
                <strong>{q.text}</strong>
                <ul>
                  {q.options.map((option, j) => (
                    <li key={j}>
                      {q.correct.includes("ABCDE"[j]) ? "✓" : "○"} {"ABCDE"[j]}.{" "}
                      {option}
                    </li>
                  ))}
                </ul>
                <small>
                  {t("score")}: {q.score}
                </small>
              </li>
            ))}
          </ol>
          {action.error != null && <ErrorState error={action.error} />}
          <div className="form-actions">
            <button
              disabled={action.pending}
              onClick={() => setPreview(undefined)}
            >
              {t("cancel")}
            </button>
            <button
              className="primary"
              disabled={action.pending}
              onClick={async () => {
                const result = await action.run(
                  `tests/${id}/import-questions/`,
                  { token: preview.token },
                );
                if (result.ok) setPreview(undefined);
              }}
            >
              {t("importConfirm")}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
