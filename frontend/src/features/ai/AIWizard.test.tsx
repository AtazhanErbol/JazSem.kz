import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  render,
  screen,
  fireEvent,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { AIWizard } from "./AIWizard";
import i18n from "../../i18n";

const mocks = vi.hoisted(() => ({ run: vi.fn() }));
vi.mock("../../hooks/useUnsavedChanges", () => ({
  useUnsavedChanges: () => () => {},
}));
vi.mock("../../components/RemoteSelect", () => ({ RemoteSelect: () => null }));
vi.mock("../../hooks/useAction", () => ({
  useAction: () => ({ run: mocks.run, pending: false, feedback: null }),
}));
vi.mock("../../services/api", () => ({
  api: async (path: string) => {
    if (path === "ai-status/")
      return {
        enabled: true,
        configured: true,
        worker_available: true,
        daily_budget: "0.25",
        model: "fake",
      };
    if (path.includes("/versions/"))
      return [{ id: "v1", version_number: 1, status: "PUBLISHED" }];
    if (path.includes("append-context"))
      return { version_number: 1, start_week: 4, base_status: "PUBLISHED" };
    if (path.startsWith("sources/"))
      return {
        results: [
          {
            id: "source",
            filename: "book.pdf",
            processing_status: "COMPLETED",
          },
        ],
        count: 1,
      };
    return { results: [], count: 0 };
  },
}));
afterEach(cleanup);
it("sends append target, teacher instruction and PDF range only after required selections", async () => {
  await i18n.changeLanguage("ru");
  mocks.run.mockResolvedValue({ ok: false });
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter initialEntries={["/app/ai?course=course"]}>
        <AIWizard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await screen.findByLabelText("book.pdf");
  const generate = screen.getByRole("button", {
    name: i18n.t("generate"),
  });
  expect(generate).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Версия, которую нужно дополнить"), {
    target: { value: "v1" },
  });
  fireEvent.click(screen.getByLabelText("book.pdf"));
  await screen.findByText(/Новые недели: 4–4/);
  fireEvent.change(screen.getByLabelText("Инструкция для ИИ (необязательно)"), {
    target: { value: "Создай задание и тест" },
  });
  fireEvent.change(screen.getByLabelText("Со страницы PDF"), {
    target: { value: "40" },
  });
  expect(generate).toBeDisabled();
  fireEvent.change(screen.getByLabelText("По страницу PDF включительно"), {
    target: { value: "42" },
  });
  await waitFor(() => expect(generate).toBeEnabled());
  fireEvent.click(generate);
  await waitFor(() =>
    expect(mocks.run).toHaveBeenCalledWith(
      "ai-jobs/",
      expect.objectContaining({
        mode: "APPEND",
        base_version: "v1",
        weeks: 1,
        instruction: "Создай задание и тест",
        page_from: 40,
        page_to: 42,
      }),
    ),
  );
  cache.clear();
});
