import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import "../i18n";
import { Shell } from "./Shell";

const actor = vi.hoisted(() => ({ role: "TEACHER" }));
vi.mock("../app/Auth", () => ({
  useUser: () => ({
    role: actor.role,
    first_name: "Test",
    last_name: "Teacher",
    email: "synthetic@example.test",
  }),
}));
beforeEach(() => {
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
});
for (const role of ["TEACHER", "ADMIN", "STUDENT"]) {
  it(`renders only permitted navigation groups for ${role}`, () => {
    actor.role = role;
    const cache = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const router = createMemoryRouter(
      [
        {
          path: "/app",
          element: <Shell />,
          children: [{ index: true, element: <p>Workspace content</p> }],
        },
      ],
      { initialEntries: ["/app"] },
    );
    render(
      <QueryClientProvider client={cache}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    expect(screen.getByText("Workspace content")).toBeTruthy();
    const urls = screen
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    expect(urls.filter((url) => url === "/app/courses")).toHaveLength(1);
    expect(urls.includes("/app/audit")).toBe(role === "ADMIN");
    expect(urls.includes("/app/ai")).toBe(role !== "STUDENT");
  });
}
