import { createContext, useContext, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, Navigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, ApiError } from "../services/api";
import type { User } from "../entities/types";
import { Loading, ErrorState } from "../components/UI";

const AuthContext = createContext<User | null>(null);
export function RoleGate({
  children,
  roles,
}: {
  children: ReactNode;
  roles: string[];
}) {
  const user = useUser();
  const { t } = useTranslation();
  return roles.includes(user.role) ? (
    children
  ) : (
    <section className="panel">
      <h1>{t("accessDenied")}</h1>
      <p>{t("accessDeniedHint")}</p>
      <Link className="button" to="/app">
        {t("home")}
      </Link>
    </section>
  );
}
export function useUser() {
  const user = useContext(AuthContext);
  if (!user) throw new Error("Authentication required");
  return user;
}
export function Protected({ children }: { children: ReactNode }) {
  const location = useLocation();
  const query = useQuery({
    queryKey: ["me"],
    queryFn: () => api<User>("auth/me/"),
    retry: false,
  });
  if (query.isPending) return <Loading />;
  if (query.error) {
    if (
      query.error instanceof ApiError &&
      [401, 403].includes(query.error.status)
    )
      return <Navigate to="/login" replace />;
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  }
  if (
    query.data.must_change_password &&
    location.pathname != "/change-temporary-password"
  )
    return <Navigate to="/change-temporary-password" replace />;
  return (
    <AuthContext.Provider value={query.data}>{children}</AuthContext.Provider>
  );
}
