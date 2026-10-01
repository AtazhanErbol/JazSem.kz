import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Download, Upload } from "lucide-react";
import { api } from "../../services/api";
import { useAction } from "../../hooks/useAction";
import { Modal, ErrorState } from "../../components/UI";
type Preview = {
  token: string;
  users: {
    email: string;
    first_name: string;
    last_name: string;
    role: string;
    preferred_language: string;
    owner_teacher: string | null;
    owner_teacher_email: string;
  }[];
};
export function UserImport() {
  const { t } = useTranslation();
  const action = useAction();
  const [preview, setPreview] = useState<Preview>();
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  return (
    <section className="panel test-import">
      <h2>{t("userImport.title")}</h2>
      <p>{t("userImport.hint")}</p>
      <div className="row-actions">
        <a className="button" href="/api/v1/users/import-template/">
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
                  await api<Preview>("users/import-preview/", "POST", form),
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
          <p>{t("userImport.summary", { count: preview.users.length })}</p>
          <ol className="import-preview">
            {preview.users.map((account) => (
              <li key={account.email}>
                <strong>
                  {account.first_name} {account.last_name}
                </strong>
                <p>
                  {account.email} ·{" "}
                  {t(account.role === "TEACHER" ? "teachers" : "students")} ·{" "}
                  {account.preferred_language.toUpperCase()}
                </p>
                {account.role === "STUDENT" && (
                  <small>
                    {t(
                      account.owner_teacher
                        ? "userImport.assigned"
                        : "userImport.unassigned",
                    )}
                    {account.owner_teacher_email &&
                      ` ${account.owner_teacher_email}`}
                  </small>
                )}
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
                  "users/import-users/",
                  { token: preview.token },
                  "POST",
                  t("userImport.success", { count: preview.users.length }),
                );
                if (result.ok) setPreview(undefined);
              }}
            >
              {t("userImport.confirm")}
            </button>
          </div>
        </Modal>
      )}
    </section>
  );
}
