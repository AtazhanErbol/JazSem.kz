import { beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
it("published version offers editing but never deletion", () => {
  state.status = "PUBLISHED";
  show();
  expect(
    screen.getByRole("button", { name: "Редактировать опубликованный курс" }),
  ).toBeEnabled();
  expect(
    screen.queryByRole("button", { name: "Удалить черновик" }),
  ).not.toBeInTheDocument();
});
