import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { Logo, Language } from "../../components/UI";
import { useAction } from "../../hooks/useAction";
import type { User } from "../../entities/types";
import { ApiError } from "../../services/api";

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
  const schema = z
    .object({
      email:
        mode === "login" || mode === "forgot"
          ? z.email(t("ux.invalidEmail"))
          : z.string(),
      password:
        mode === "forgot"
          ? z.string()
          : z
              .string()
              .min(
                mode === "login" ? 1 : 8,
                t(mode === "login" ? "ux.required" : "ux.passwordLength"),
              ),
      current_password: z.string(),
      confirm_password: z.string(),
    })
    .refine(
      (data) =>
        !["reset", "change"].includes(mode) ||
        data.password === data.confirm_password,
      { message: t("passwordMismatch"), path: ["confirm_password"] },
    );
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: "",
      password: "",
      current_password: "",
      confirm_password: "",
    },
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
    const result = await action.run<User>(
      `auth/${endpoint}/`,
      mode === "login"
        ? { email: data.email, password: data.password }
        : mode === "forgot"
          ? { email: data.email }
          : mode === "change"
            ? {
                password: data.password,
                current_password: data.current_password,
              }
            : {
                password: data.password,
                uid: params.get("uid") ?? "",
                token: params.get("token") ?? "",
              },
      "POST",
      mode === "forgot" ? t("resetEmailSent") : undefined,
    );
    if (!result.ok && result.error instanceof ApiError) {
      for (const [key, message] of Object.entries(result.error.fieldErrors)) {
        if (key in data)
          form.setError(key as keyof typeof data, { message: String(message) });
      }
    }
    if (result.ok && mode === "login") {
      cache.setQueryData(["me"], result.data);
      nav(
        result.data.must_change_password
          ? "/change-temporary-password"
          : "/app",
      );
    } else if (result.ok && mode !== "forgot") {
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
        {mode === "forgot" && <p className="muted">{t("forgotHint")}</p>}
        <form onSubmit={form.handleSubmit(submit)}>
          {(mode === "login" || mode === "forgot") && (
            <label>
              {t("email")}
              <input
                type="email"
                autoComplete="username"
                aria-invalid={!!form.formState.errors.email}
                aria-describedby={
                  form.formState.errors.email ? "email-error" : undefined
                }
                {...form.register("email")}
              />
              {form.formState.errors.email && (
                <span className="field-error" id="email-error" role="alert">
                  {form.formState.errors.email?.message}
                </span>
              )}
            </label>
          )}
          {mode === "change" && (
            <label>
              {t("current_password")}
              <input
                type="password"
                autoComplete="current-password"
                aria-invalid={!!form.formState.errors.current_password}
                aria-describedby={
                  form.formState.errors.current_password
                    ? "current_password-error"
                    : undefined
                }
                {...form.register("current_password")}
              />
              {form.formState.errors.current_password && (
                <span
                  className="field-error"
                  id="current_password-error"
                  role="alert"
                >
                  {form.formState.errors.current_password?.message}
                </span>
              )}
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
                aria-invalid={!!form.formState.errors.password}
                aria-describedby={
                  form.formState.errors.password ? "password-error" : undefined
                }
                {...form.register("password")}
              />
              {form.formState.errors.password && (
                <span className="field-error" id="password-error" role="alert">
                  {form.formState.errors.password?.message}
                </span>
              )}
            </label>
          )}
          {["reset", "change"].includes(mode) && (
            <label>
              {t("confirmPassword")}
              <input
                type="password"
                autoComplete="new-password"
                aria-invalid={!!form.formState.errors.confirm_password}
                aria-describedby={
                  form.formState.errors.confirm_password
                    ? "confirm_password-error"
                    : undefined
                }
                {...form.register("confirm_password")}
              />
              {form.formState.errors.confirm_password && (
                <span
                  className="field-error"
                  id="confirm_password-error"
                  role="alert"
                >
                  {form.formState.errors.confirm_password?.message}
                </span>
              )}
            </label>
          )}
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
