import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../services/api";
import { ErrorState } from "../components/UI";
import { affectedQueries, queryKeys } from "../services/queryKeys";
import type { Attempt } from "../entities/types";

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
      const [resource, id, verb] = path.split("/");
      if (resource === "attempts" && verb === "answer") {
        const answer = body as { question: string; selected_options: string[] };
        cache.setQueryData<Attempt>(queryKeys.detail("attempts", id), (old) =>
          old
            ? {
                ...old,
                answers: {
                  ...old.answers,
                  [answer.question]: answer.selected_options,
                },
              }
            : old,
        );
      }
      await Promise.all(
        affectedQueries(path).map((root) =>
          cache.invalidateQueries({ queryKey: [root] }),
        ),
      );
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
    error,
    feedback: (
      <>
        {error !== undefined && (
          <ErrorState error={error} title={t("actionFailed")} />
        )}
        <div className="feedback" role="status">
          {success}
        </div>
      </>
    ),
  };
}
