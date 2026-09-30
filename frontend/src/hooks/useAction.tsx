import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../services/api";
import { ErrorState } from "../components/UI";

export function useAction() {
  const running = useRef(false);
  const cache = useQueryClient();
  const { t } = useTranslation();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const [success, setSuccess] = useState("");
  async function run<T>(
    path: string,
    body?: unknown,
    method = "POST",
    successMessage?: string,
  ): Promise<{ ok: true; data: T } | { ok: false; error: unknown }> {
    if (running.current) return { ok: false, error: new Error(t("loading")) };
    running.current = true;
    setPending(true);
    setError(undefined);
    setSuccess("");
    try {
      const result = await api<T>(path, method, body);
      // Protected refetches during logout can redirect the next session
      // after a delayed 403. Session changes have their own cache handling.
      if (!path.startsWith("auth/")) await cache.invalidateQueries();
      else if (path === "auth/change-password/" || path === "auth/me/")
        await cache.invalidateQueries({ queryKey: ["me"] });
      setSuccess(successMessage ?? t("saved"));
      return { ok: true, data: result };
    } catch (e) {
      setError(e);
      return { ok: false, error: e };
    } finally {
      setPending(false);
      running.current = false;
    }
  }
  return {
    run,
    pending,
    feedback: (
      <>
        {error !== undefined && <ErrorState error={error} />}
        <div className="feedback" role="status">
          {success}
        </div>
      </>
    ),
  };
}
