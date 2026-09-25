import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "../../i18n";
import { AuthPage } from "./AuthPage";

beforeEach(() => vi.restoreAllMocks());
function setup() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <AuthPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
describe("login form", () => {
  it("validates email before any request", async () => {
    const fetch = vi.spyOn(globalThis, "fetch");
    setup();
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "invalid" },
    });
    fireEvent.submit(
      screen.getByRole("button", { name: "Войти" }).closest("form")!,
    );
    await waitFor(() =>
      expect(screen.getAllByRole("alert").length).toBeGreaterThan(0),
    );
    expect(fetch).not.toHaveBeenCalled();
  });
  it("surfaces server authentication errors", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrfToken: "token" }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ message: "Неверный email или пароль.", errors: {} }),
          { status: 400, headers: { "Content-Type": "application/json" } },
        ),
      );
    setup();
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "student@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Пароль"), {
      target: { value: "wrong-password" },
    });
    fireEvent.submit(
      screen.getByRole("button", { name: "Войти" }).closest("form")!,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Неверный email или пароль.",
    );
  });
});
