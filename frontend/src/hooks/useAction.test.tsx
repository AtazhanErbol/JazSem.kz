import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { api, ApiError } from "../services/api";
import { useAction } from "./useAction";
import "../i18n";

vi.mock("../services/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/api")>()),
  api: vi.fn(),
}));
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>
    {children}
  </QueryClientProvider>
);

it("distinguishes a successful empty 204 response from a failed mutation", async () => {
  const hook = renderHook(() => useAction(), { wrapper });
  vi.mocked(api).mockResolvedValueOnce(undefined);
  let outcome;
  await act(async () => {
    outcome = await hook.result.current.run("users/id/deactivate/");
  });
  expect(outcome).toEqual({ ok: true, data: undefined });
  const error = new ApiError(403, "Denied");
  vi.mocked(api).mockRejectedValueOnce(error);
  await act(async () => {
    outcome = await hook.result.current.run("users/id/deactivate/");
  });
  expect(outcome).toEqual({ ok: false, error });
  expect(hook.result.current.pending).toBe(false);
});

it("prevents duplicate in-flight submission while preserving server field errors", async () => {
  const hook = renderHook(() => useAction(), { wrapper });
  const error = new ApiError(400, "Invalid", {
    owner_teacher: "Choose an active teacher",
  });
  let reject!: (reason: unknown) => void;
  vi.mocked(api).mockImplementationOnce(
    () =>
      new Promise((_, fail) => {
        reject = fail;
      }),
  );
  const calls = vi.mocked(api).mock.calls.length;
  await act(async () => {
    const pending = hook.result.current.run("users/", {});
    expect((await hook.result.current.run("users/", {})).ok).toBe(false);
    reject(error);
    const result = await pending;
    expect(result.ok).toBe(false);
    if (!result.ok)
      expect((result.error as ApiError).fieldErrors.owner_teacher).toBe(
        "Choose an active teacher",
      );
  });
  expect(vi.mocked(api).mock.calls.length - calls).toBe(1);
});

it("saves an answer in the visible attempt without refetching unrelated screens", async () => {
  const cache = new QueryClient();
  const attemptKey = ["attempts", "detail", "attempt-one"];
  cache.setQueryData(attemptKey, {
    id: "attempt-one",
    answers: { q1: ["old"] },
    status: "IN_PROGRESS",
  });
  cache.setQueryData(["tree", "course"], { weeks: [] });
  cache.setQueryData(["dashboard"], { courses: 1 });
  const invalidation = vi.spyOn(cache, "invalidateQueries");
  const hook = renderHook(() => useAction(), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={cache}>{children}</QueryClientProvider>
    ),
  });
  vi.mocked(api).mockResolvedValueOnce({ saved: true });
  await act(async () => {
    await hook.result.current.run("attempts/attempt-one/answer/", {
      question: "q1",
      selected_options: ["new"],
    });
  });
  expect(cache.getQueryData(attemptKey)).toMatchObject({
    answers: { q1: ["new"] },
  });
  expect(invalidation).not.toHaveBeenCalled();
  vi.mocked(api).mockRejectedValueOnce(new ApiError(0, "Offline"));
  await act(async () => {
    await hook.result.current.run("attempts/attempt-one/answer/", {
      question: "q1",
      selected_options: ["lost"],
    });
  });
  expect(cache.getQueryData(attemptKey)).toMatchObject({
    answers: { q1: ["new"] },
  });
});
