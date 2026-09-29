import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { LockKeyhole, UserRound, ArrowUpRight } from "lucide-react";
import { useUser } from "../../app/Auth";
import { useAction } from "../../hooks/useAction";

export function Settings() {
  const user = useUser();
  const { t, i18n } = useTranslation();
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
      <p className="muted">{t("profileHint")}</p>
      <div className="settings-layout">
        <section className="panel">
          <div className="settings-section-title">
            <UserRound size={22} />
            <h2>{t("personalDetails")}</h2>
          </div>
          <form
            onSubmit={form.handleSubmit(async (data) => {
              const result = await action.run("auth/me/", data, "PATCH");
              if (result) {
                localStorage.setItem("language", data.preferred_language);
                await i18n.changeLanguage(data.preferred_language);
              }
            })}
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
                <option value="ru">Русский</option>
                <option value="kk">Қазақша</option>
              </select>
            </label>
            <button className="primary" disabled={action.pending}>
              {t("save")}
            </button>
            {action.feedback}
          </form>
        </section>
        <section className="panel security-card">
          <div className="settings-section-title">
            <LockKeyhole size={22} />
            <h2>{t("accountSecurity")}</h2>
          </div>
          <p>{t("passwordHint")}</p>
          <Link className="button" to="/change-temporary-password">
            {t("changePassword")} <ArrowUpRight size={18} />
          </Link>
        </section>
      </div>
    </>
  );
}
