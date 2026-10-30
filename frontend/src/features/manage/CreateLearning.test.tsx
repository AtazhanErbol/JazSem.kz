import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import i18n from "../../i18n";
import { api } from "../../services/api";
import { ActivityCreate } from "./CreateLearning";

vi.mock("../../services/api", async (original) => ({
  ...(await original<typeof import("../../services/api")>()),
  api: vi.fn(),
}));
vi.mock("../../app/Auth", () => ({
  useUser: () => ({ id: "admin", role: "ADMIN" }),
}));
vi.mock("../../hooks/useUnsavedChanges", () => ({
  useUnsavedChanges: () => () => {},
}));
vi.mock("../../components/RemoteSelect", () => ({
  RemoteSelect: ({
    label,
    value,
    onChange,
  }: {
    label: string;
    value: string;
    onChange: (value: string) => void;
  }) => (
    <select
      aria-label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="">—</option>
      <option value="course">New course</option>
    </select>
  ),
}));
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("continues from a new week to its topic when tree refetch renders before mutation completion", async () => {
  await i18n.changeLanguage("ru");
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  let weeks: unknown[] = [];
  vi.mocked(api).mockImplementation(async (path, method = "GET") => {
    if (path.endsWith("/versions/"))
      return [{ id: "draft", status: "DRAFT", version_number: 1 }];
    if (path.includes("/tree/"))
      return { course: { title: "New course" }, weeks };
    if (path === "weeks/" && method === "POST") {
      const week = { id: "week", number: 1, title: "Basics", topics: [] };
      weeks = [week];
      return week;
    }
    if (path === "topics/" && method === "POST") {
      const topic = { id: "topic", title: "Equations" };
      weeks = [{ id: "week", number: 1, title: "Basics", topics: [topic] }];
      return topic;
    }
    throw new Error(`Unexpected test API path: ${path}`);
  });
  const invalidate = cache.invalidateQueries.bind(cache);
  vi.spyOn(cache, "invalidateQueries").mockImplementation(async (...args) => {
    await invalidate(...args);
    // Commit the refreshed tree while RecordForm still awaits useAction.run.
    await new Promise((resolve) => setTimeout(resolve, 20));
  });
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter>
        <ActivityCreate resource="assignments" onClose={() => {}} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  fireEvent.change(screen.getByLabelText("Выберите курс"), {
    target: { value: "course" },
  });
  fireEvent.click(
    await screen.findByRole("button", { name: /Добавить неделю/ }),
  );
  fireEvent.change(screen.getByLabelText("Название"), {
    target: { value: "Basics" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
  fireEvent.click(await screen.findByRole("button", { name: /Добавить тему/ }));
  fireEvent.change(screen.getByLabelText("Название"), {
    target: { value: "Equations" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
  const next = screen.getByRole("button", {
    name: "Далее: содержание и настройки",
  });
  await waitFor(() => expect(next).toBeEnabled());
  fireEvent.click(next);
  fireEvent.click(
    screen.getByRole("button", { name: "Содержание и инструкция" }),
  );
  expect(screen.getByLabelText("Инструкция")).toBeInTheDocument();
  cache.clear();
});
