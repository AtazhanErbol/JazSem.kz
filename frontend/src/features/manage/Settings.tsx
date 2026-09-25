import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useUser } from "../../app/Auth";
import { useAction } from "../../hooks/useAction";

export function Settings() {
  const user = useUser();
  const { t } = useTranslation();
  const form = useForm({
    defaultValues: {
      first_name: user.first_name,
      last_name: user.last_name,
      preferred_language: user.preferred_language,
    },
  });
  const action = useAction();
  return (
    <>
      <h1>{t("settings")}</h1>
      <p>{t("settingsHint")}</p>
      <section className="panel">
        <form
          onSubmit={form.handleSubmit((data) =>
            action.run("auth/me/", data, "PATCH"),
          )}
        >
          <label>
            {t("first_name")}
            <input {...form.register("first_name")} />
          </label>
          <label>
            {t("last_name")}
            <input {...form.register("last_name")} />
          </label>
          <label>
            {t("preferred_language")}
            <select {...form.register("preferred_language")}>
              <option value="ru">RU</option>
              <option value="kk">KZ</option>
            </select>
          </label>
          <button className="primary" disabled={action.pending}>
            {t("save")}
          </button>
          {action.feedback}
        </form>
        <Link to="/change-temporary-password">{t("changePassword")}</Link>
      </section>
    </>
  );
}
