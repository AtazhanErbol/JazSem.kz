import { beforeEach, it, expect, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
  within,
} from "@testing-library/react";
import { TestImport } from "./TestImport";
import i18n from "../../i18n";
const mocks = vi.hoisted(() => ({ api: vi.fn(), run: vi.fn() }));
vi.mock("../../services/api", () => ({ api: mocks.api }));
vi.mock("../../hooks/useAction", () => ({
  useAction: () => ({ run: mocks.run, pending: false, feedback: null }),
}));
beforeEach(async () => {
  cleanup();
  vi.clearAllMocks();
  await i18n.changeLanguage("ru");
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
it("previews an uploaded workbook before appending questions", async () => {
  mocks.api.mockResolvedValue({
    token: "signed",
    existing: 3,
    questions: [
      { text: "Question", options: ["One", "Two"], correct: ["B"], score: 1 },
    ],
  });
  mocks.run.mockResolvedValue({ ok: true });
  render(<TestImport id="test" />);
  fireEvent.change(screen.getByLabelText("Загрузить Excel"), {
    target: { files: [new File(["xlsx"], "quiz.xlsx")] },
  });
  await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
  expect(mocks.run).not.toHaveBeenCalled();
  expect(screen.getByText(/Уже в тесте: 3/)).toBeInTheDocument();
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "Добавить вопросы",
    }),
  );
  await waitFor(() =>
    expect(mocks.run).toHaveBeenCalledWith("tests/test/import-questions/", {
      token: "signed",
    }),
  );
});
