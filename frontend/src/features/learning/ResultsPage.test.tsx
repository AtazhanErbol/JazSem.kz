import { beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import i18n from "../../i18n";
import { ResultsPage } from "./ResultsPage";

const { query } = vi.hoisted(() => ({ query: vi.fn() }));
vi.mock("@tanstack/react-query", () => ({ useQuery: query }));
vi.mock("../manage/ResourceFilters", () => ({ ResourceFilters: () => null }));
const row = {
  id: "enrollment",
  course: "course",
  course_title: "Алгебра",
  student_name: "Тестовый студент",
  progress: { percent: 50, completed: 3, total: 6 },
  grades: {
    score: 62,
    components: [
      { kind: "ASSIGNMENTS", weight: 60, score: 50 },
      { kind: "TESTS", weight: 40, score: 80 },
    ],
  },
};
beforeEach(async () => {
  cleanup();
  await i18n.changeLanguage("ru");
  query.mockReturnValue({ data: { count: 1, results: [row] } });
});
it("distinguishes category averages from their weighted contributions", () => {
  render(
    <MemoryRouter>
      <ResultsPage mode="grades" />
    </MemoryRouter>,
  );
  const category = screen.getByRole("heading", {
    name: "Задания",
  }).parentElement!;
  expect(within(category).getByText("50 / 100")).toBeInTheDocument();
  expect(within(category).getByText("60%")).toBeInTheDocument();
  expect(within(category).getByText("30 / 60")).toBeInTheDocument();
  expect(screen.getByText("32 / 40")).toBeInTheDocument();
  expect(screen.getByText("Студент: Тестовый студент")).toBeInTheDocument();
});
it("explains completion separately from grades", () => {
  render(
    <MemoryRouter>
      <ResultsPage mode="progress" />
    </MemoryRouter>,
  );
  expect(
    screen.getByText("Выполнено 3 из 6 обязательных элементов"),
  ).toBeInTheDocument();
  expect(screen.getByRole("progressbar")).toHaveAttribute(
    "aria-valuenow",
    "50",
  );
  expect(screen.queryByText("Текущий итоговый балл")).not.toBeInTheDocument();
});
it("explains an empty course instead of showing an unexplained 0 / 0", () => {
  query.mockReturnValue({
    data: {
      count: 1,
      results: [{ ...row, progress: { percent: 0, completed: 0, total: 0 } }],
    },
  });
  render(
    <MemoryRouter>
      <ResultsPage mode="progress" />
    </MemoryRouter>,
  );
  expect(
    screen.getByText("Обязательные элементы пока не добавлены."),
  ).toBeInTheDocument();
});
