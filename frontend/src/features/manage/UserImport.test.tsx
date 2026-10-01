import { beforeEach, it, expect, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
  within,
} from "@testing-library/react";
import { UserImport } from "./UserImport";
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
it("previews users before creating accounts and invitations", async () => {
  mocks.api.mockResolvedValue({
    token: "signed",
    users: [
      {
        email: "new@example.test",
        first_name: "New",
        last_name: "Student",
        role: "STUDENT",
        preferred_language: "ru",
        owner_teacher: null,
        owner_teacher_email: "",
      },
    ],
  });
  mocks.run.mockResolvedValue({ ok: true });
  render(<UserImport />);
  fireEvent.change(screen.getByLabelText("Загрузить Excel"), {
    target: { files: [new File(["xlsx"], "quiz.xlsx")] },
  });
  await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
  expect(mocks.run).not.toHaveBeenCalled();
  expect(screen.getByText(/new@example.test/)).toBeInTheDocument();
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "Добавить и отправить приглашения",
    }),
  );
  await waitFor(() =>
    expect(mocks.run).toHaveBeenCalledWith(
      "users/import-users/",
      { token: "signed" },
      "POST",
      expect.any(String),
    ),
  );
});
