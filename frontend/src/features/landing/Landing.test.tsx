import { beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import i18n from "../../i18n";
import { Landing } from "./Landing";
const { query } = vi.hoisted(() => ({ query: vi.fn() }));
vi.mock("@tanstack/react-query", () => ({ useQuery: query }));
vi.mock("./useLandingMotion", () => ({
  useLandingMotion: () => ({ root: { current: null }, scrolled: false }),
}));
vi.mock("./BookScene", () => ({ BookScene: () => <div data-testid="book" /> }));
beforeEach(async () => {
  cleanup();
  await i18n.changeLanguage("ru");
});
it("keeps the original landing when no published override exists", () => {
  query.mockImplementation(({ queryKey }) => ({
    data:
      queryKey[0] === "landing-settings"
        ? { texts: {}, hidden: [], image: "" }
        : { results: [] },
  }));
  render(
    <MemoryRouter>
      <Landing />
    </MemoryRouter>,
  );
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
    "Продолжайте учиться.",
  );
  expect(screen.getByTestId("book")).toBeInTheDocument();
  expect(
    screen.getByRole("heading", {
      name: "Учебная неделя. Всё на своих местах.",
    }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Создайте самостоятельно" }),
  ).toBeInTheDocument();
});
it("renders published text, image and section visibility without interpreting HTML", () => {
  query.mockImplementation(({ queryKey }) => ({
    data:
      queryKey[0] === "landing-settings"
        ? {
            texts: {
              heroTitle: "<b>Наш курс</b>",
              imageAlt: "Учебная иллюстрация",
              featuresTitle: "Наш учебный процесс",
            },
            hidden: ["faq", "learning", "creation"],
            image: "https://example.test/cover.png",
          }
        : { results: [] },
  }));
  render(
    <MemoryRouter>
      <Landing />
    </MemoryRouter>,
  );
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
    "<b>Наш курс</b>",
  );
  expect(
    screen.getByRole("img", { name: "Учебная иллюстрация" }),
  ).toHaveAttribute("src", "https://example.test/cover.png");
  expect(screen.queryByText("Вопросы и ответы")).not.toBeInTheDocument();
  expect(screen.queryByTestId("book")).not.toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Наш учебный процесс" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", {
      name: "Учебная неделя. Всё на своих местах.",
    }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Создайте самостоятельно" }),
  ).not.toBeInTheDocument();
});
