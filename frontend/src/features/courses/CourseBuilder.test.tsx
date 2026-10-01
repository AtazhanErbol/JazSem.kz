import { beforeEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import i18n from "../../i18n";
import { CourseBuilder } from "./CourseBuilder";
const state = vi.hoisted(() => ({ status: "DRAFT", run: vi.fn() }));
vi.mock("../../hooks/useAction", () => ({
  useAction: () => ({ run: state.run, pending: false, feedback: null }),
}));
vi.mock("./CourseSharing", () => ({ CourseSharing: () => null }));
vi.mock("../../components/UI", () => ({
  Badge: ({ children }: { children: React.ReactNode }) => (
    <span>{children}</span>
  ),
  Empty: () => null,
  Loading: () => null,
  ErrorState: () => null,
  Modal: ({ children }: { children: React.ReactNode }) => (
    <div role="dialog">{children}</div>
  ),
}));
vi.mock("@tanstack/react-query", () => ({
  useQuery: ({ queryKey }: { queryKey: string[] }) => ({
    data:
      queryKey[0] === "versions"
        ? [{ id: "v1", status: state.status, version_number: 1 }]
        : {
            course: { id: "c1", title: "Mathematics", teacher: "t1" },
            version: { id: "v1", version_number: 1, status: state.status },
            weeks: [],
            scheme: null,
            components: [],
          },
  }),
}));
beforeEach(async () => {
  cleanup();
  state.status = "DRAFT";
  state.run.mockReset();
  await i18n.changeLanguage("ru");
});
function show() {
  render(
    <MemoryRouter initialEntries={["/app/courses/c1"]}>
      <Routes>
        <Route path="/app/courses/:id" element={<CourseBuilder />} />
      </Routes>
    </MemoryRouter>,
  );
}
it("requires exact draft title and version before deleting", () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: "Удалить черновик" }));
  const buttons = screen.getAllByRole("button", { name: "Удалить черновик" });
  expect(buttons[1]).toBeDisabled();
  const input = screen.getByRole("textbox");
  fireEvent.change(input, { target: { value: "Mathematics" } });
  expect(buttons[1]).toBeDisabled();
  fireEvent.change(input, { target: { value: "Mathematics · v1" } });
  expect(buttons[1]).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "Отмена" }));
  expect(state.run).not.toHaveBeenCalled();
});
it("published version offers editing and confirmed deletion", () => {
  state.status = "PUBLISHED";
  show();
  expect(
    screen.getByRole("button", { name: "Редактировать опубликованный курс" }),
  ).toBeEnabled();
  expect(
    screen.queryByRole("button", { name: "Удалить черновик" }),
  ).not.toBeInTheDocument();
});

it("requires exact confirmation for published deletion", () => {
  state.status = "PUBLISHED";
  show();
  fireEvent.click(
    screen.getByRole("button", { name: "Удалить опубликованную версию" }),
  );
  const buttons = screen.getAllByRole("button", {
    name: "Удалить опубликованную версию",
  });
  expect(buttons[1]).toBeDisabled();
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "Mathematics · v1" },
  });
  expect(buttons[1]).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "Отмена" }));
  expect(state.run).not.toHaveBeenCalled();
});

it("previews the student update and applies only after confirmation", async () => {
  state.status = "PUBLISHED";
  state.run
    .mockResolvedValueOnce({
      ok: true,
      data: { students: 2, groups: 1, version_number: 2 },
    })
    .mockResolvedValueOnce({ ok: true });
  show();
  fireEvent.click(screen.getByRole("button", { name: "Обновить у студентов" }));
  await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
  expect(state.run).toHaveBeenCalledTimes(1);
  expect(state.run.mock.calls[0][0]).toBe(
    "courses/c1/update-students-preview/",
  );
  expect(screen.getByText(/студентов — 2, групп — 1/)).toBeInTheDocument();
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "Подтвердить",
    }),
  );
  await waitFor(() =>
    expect(state.run.mock.calls[1][0]).toBe("courses/c1/update-students/"),
  );
});
