import { createContext, useContext, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Navigate, useLocation } from "react-router-dom";
import { api, ApiError } from "../services/api";
import type { User } from "../entities/types";
import { Loading, ErrorState } from "../components/UI";

const AuthContext = createContext<User | null>(null);
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
