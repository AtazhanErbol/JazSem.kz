import { beforeEach, expect, it, vi } from "vitest";

beforeEach(() => {
  vi.resetModules();
  vi.unstubAllGlobals();
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
