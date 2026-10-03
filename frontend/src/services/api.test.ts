import { beforeEach, expect, it, vi } from "vitest";

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  vi.resetModules();
  vi.unstubAllGlobals();
  document.cookie = "csrftoken=; Max-Age=0; path=/";
});

it("explains network and proxy failures without exposing raw HTML", async () => {
  const { api } = await import("./api");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
  );
  await expect(api("courses/")).rejects.toMatchObject({ status: 0 });
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response("<html>proxy error</html>", { status: 502 }),
      ),
  );
  await expect(api("courses/")).rejects.not.toThrow("<html>");
});

it("refreshes CSRF after login rotates the token", async () => {
  const { api } = await import("./api");
  const json = (body: unknown) =>
    new Response(JSON.stringify(body), {
      headers: { "content-type": "application/json" },
    });
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(json({ csrfToken: "old" }))
    .mockResolvedValueOnce(json({ id: "user" }))
    .mockResolvedValueOnce(json({ csrfToken: "new" }))
    .mockResolvedValueOnce(json({ id: "course" }));
  vi.stubGlobal("fetch", fetcher);
  await api("auth/login/", "POST", {});
  await api("courses/", "POST", {});
  expect(fetcher.mock.calls[3][1].headers["X-CSRFToken"]).toBe("new");
});

it.each([false, true])(
  "refreshes a rejected token once, preserving the original action (upload=%s)",
  async (upload) => {
    const { api } = await import("./api");
    const body = upload ? new FormData() : { title: "Original title" };
    if (body instanceof FormData)
      body.append("file", new Blob(["notes"]), "notes.txt");
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(json({ csrfToken: "old" }))
      .mockResolvedValueOnce(json({ code: "csrf_failed" }, 403))
      .mockResolvedValueOnce(json({ csrfToken: "fresh" }))
      .mockResolvedValueOnce(json({ id: "saved" }));
    vi.stubGlobal("fetch", fetcher);
    await expect(api("materials/", "POST", body)).resolves.toEqual({
      id: "saved",
    });
    const rejected = fetcher.mock.calls[1][1];
    const retried = fetcher.mock.calls[3][1];
    expect(retried.body).toBe(rejected.body);
    expect(retried.headers["X-CSRFToken"]).toBe("fresh");
    expect(fetcher.mock.calls[2][1].cache).toBe("no-store");
    if (upload) expect(retried.headers).not.toHaveProperty("Content-Type");
    expect(fetcher).toHaveBeenCalledTimes(4);
  },
);

it("reads the current cookie when another tab rotates CSRF", async () => {
  const { api } = await import("./api");
  const fetcher = vi
    .fn()
    .mockImplementation(() => Promise.resolve(json({ saved: true })));
  vi.stubGlobal("fetch", fetcher);
  document.cookie = "csrftoken=first; path=/";
  await api("auth/me/", "PATCH", { first_name: "One" });
  document.cookie = "csrftoken=rotated; path=/";
  await api("auth/me/", "PATCH", { first_name: "Two" });
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(fetcher.mock.calls[1][1].headers["X-CSRFToken"]).toBe("rotated");
});

it("shares one token initialization between concurrent actions", async () => {
  const { api } = await import("./api");
  const fetcher = vi
    .fn()
    .mockImplementation((url: string) =>
      Promise.resolve(
        json(
          url.endsWith("auth/login/")
            ? { csrfToken: "shared" }
            : { saved: true },
        ),
      ),
    );
  vi.stubGlobal("fetch", fetcher);
  await Promise.all([
    api("courses/", "POST", {}),
    api("materials/", "POST", {}),
  ]);
  expect(
    fetcher.mock.calls.filter(([url]) => url.endsWith("auth/login/")),
  ).toHaveLength(1);
  expect(fetcher).toHaveBeenCalledTimes(3);
});

it.each([
  [403, "permission_denied"],
  [503, "service_unavailable"],
  [400, "invalid"],
])("does not replay actions after status %s (%s)", async (status, code) => {
  const { api } = await import("./api");
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(json({ csrfToken: "token" }))
    .mockResolvedValueOnce(json({ code }, status));
  vi.stubGlobal("fetch", fetcher);
  await expect(api("courses/", "POST", {})).rejects.toMatchObject({
    status,
    code,
  });
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("does not replay an action after an ambiguous network failure", async () => {
  const { api } = await import("./api");
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(json({ csrfToken: "token" }))
    .mockRejectedValueOnce(new TypeError("Failed to fetch"));
  vi.stubGlobal("fetch", fetcher);
  await expect(api("courses/", "POST", {})).rejects.toMatchObject({
    status: 0,
  });
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("stops after one refresh when CSRF is still rejected", async () => {
  const { api } = await import("./api");
  const fetcher = vi
    .fn()
    .mockImplementation((_url: string, options: RequestInit) =>
      Promise.resolve(
        json(
          options.method !== "POST"
            ? { csrfToken: "token" }
            : { code: "csrf_failed" },
          options.method !== "POST" ? 200 : 403,
        ),
      ),
    );
  vi.stubGlobal("fetch", fetcher);
  await expect(api("auth/login/", "POST", {})).rejects.toMatchObject({
    status: 403,
    code: "csrf_failed",
  });
  expect(fetcher).toHaveBeenCalledTimes(4);
});

it("allows token initialization again after a temporary fetch failure", async () => {
  const { api } = await import("./api");
  const fetcher = vi
    .fn()
    .mockRejectedValueOnce(new TypeError("Offline"))
    .mockResolvedValueOnce(json({ csrfToken: "token" }))
    .mockResolvedValueOnce(json({ saved: true }));
  vi.stubGlobal("fetch", fetcher);
  await expect(api("materials/", "POST", {})).rejects.toMatchObject({
    status: 0,
  });
  await expect(api("materials/", "POST", {})).resolves.toEqual({ saved: true });
});

it("does not request or replay a cancelled action", async () => {
  const { api } = await import("./api");
  const controller = new AbortController();
  controller.abort();
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  await expect(
    api("courses/", "POST", {}, controller.signal),
  ).rejects.toMatchObject({ name: "AbortError" });
  expect(fetcher).not.toHaveBeenCalled();
});
