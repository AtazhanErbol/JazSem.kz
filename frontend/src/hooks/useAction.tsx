import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../services/api";
import { ErrorState } from "../components/UI";

export function useAction() {
  const cache = useQueryClient();
  const { t } = useTranslation();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const [success, setSuccess] = useState("");
  async function run<T>(
    path: string,
    body?: unknown,
    method = "POST",
  ): Promise<T | undefined> {
    setPending(true);
    setError(undefined);
    setSuccess("");
    try {
      const result = await api<T>(path, method, body);
      await cache.invalidateQueries();
      setSuccess(t("saved"));
      return result;
    } catch (e) {
      setError(e);
      return undefined;
    } finally {
      setPending(false);
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
