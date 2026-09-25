import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { Logo, Language } from "../../components/UI";
import { useAction } from "../../hooks/useAction";
import type { User } from "../../entities/types";

export function AuthPage({
  mode = "login",
}: {
  mode?: "login" | "forgot" | "reset" | "change";
}) {
  const { t } = useTranslation();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const action = useAction();
  const cache = useQueryClient();
  const schema = z.object({
    email: mode === "login" || mode === "forgot" ? z.email() : z.string(),
    password:
      mode === "forgot" ? z.string() : z.string().min(mode === "login" ? 1 : 8),
    current_password: z.string(),
  });
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "", current_password: "" },
  });
  const title = {
    login: "login",
    forgot: "reset",
    reset: "changePassword",
    change: "changePassword",
  }[mode];
  async function submit(data: z.infer<typeof schema>) {
    const endpoint = {
      login: "login",
      forgot: "forgot-password",
      reset: "reset-password",
      change: "change-password",
    }[mode];
    const result = await action.run<User>(`auth/${endpoint}/`, {
      ...data,
      uid: params.get("uid"),
      token: params.get("token"),
    });
    if (result && mode === "login") {
      cache.setQueryData(["me"], result);
      nav(result.must_change_password ? "/change-temporary-password" : "/app");
    } else if (result && mode !== "forgot") {
      nav(mode === "change" ? "/app" : "/login");
    }
  }
  return (
    <div className="auth-page">
      <header>
        <Logo />
        <Language />
      </header>
      <main className="auth-card">
        <span className="eyebrow">JAZSEM / {t("app")}</span>
        <h1>{t(title)}</h1>
        <form onSubmit={form.handleSubmit(submit)}>
          {(mode === "login" || mode === "forgot") && (
            <label>
              {t("email")}
              <input
                type="email"
                autoComplete="username"
                {...form.register("email")}
              />
            </label>
          )}
          {mode === "change" && (
            <label>
              {t("current_password")}
              <input
                type="password"
                autoComplete="current-password"
                {...form.register("current_password")}
              />
            </label>
          )}
          {mode !== "forgot" && (
            <label>
              {t("password")}
              <input
                type="password"
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
                {...form.register("password")}
              />
            </label>
          )}
          {Object.entries(form.formState.errors).map(([key, error]) => (
            <p role="alert" key={key}>
              {t(key)}: {error.message}
            </p>
          ))}
          <button className="primary" disabled={action.pending}>
            {t(title)}
          </button>
          {action.feedback}
        </form>
        {mode === "login" ? (
          <Link to="/forgot-password">{t("forgot")}</Link>
        ) : (
          <Link to="/login">{t("login")}</Link>
        )}
      </main>
      <div className="auth-art">
        <span>J.</span>
        <h2>{t("heroTitle")}</h2>
        <p>{t("heroText")}</p>
      </div>
    </div>
  );
}
