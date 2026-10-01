import { beforeEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import i18n from "../../i18n";
import { CourseSharing } from "./CourseSharing";
const { run, query } = vi.hoisted(() => ({ run: vi.fn(), query: vi.fn() }));
vi.mock("@tanstack/react-query", () => ({ useQuery: query }));
vi.mock("../../hooks/useAction", () => ({
  useAction: () => ({ run, pending: false, feedback: null }),
}));
vi.mock("../../components/RemoteSelect", () => ({
  RemoteSelect: ({
    label,
    value,
    onChange,
  }: {
    label: string;
    value: string;
    onChange: (v: string) => void;
  }) => (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">Choose</option>
      <option value="one">One</option>
      <option value="two">Two</option>
    </select>
  ),
}));
beforeEach(async () => {
  cleanup();
  run.mockReset();
  query.mockReturnValue({
    data: { count: 0, results: [], selected_assigned: false },
  });
  await i18n.changeLanguage("ru");
});
it("disables assigned recipients independently and enables new selections", async () => {
  run.mockResolvedValue({ ok: true });
  render(<CourseSharing id="course" teacher="teacher" published />);
  const selectors = screen.getAllByRole("combobox");
  const buttons = screen.getAllByRole("button", { name: "Назначить" });
  expect(buttons[0]).toBeDisabled();
  expect(buttons[1]).toBeDisabled();
  for (const i of [0, 1]) {
    fireEvent.change(selectors[i], { target: { value: "one" } });
    fireEvent.click(buttons[i]);
    await waitFor(() => expect(buttons[i]).toBeDisabled());
    fireEvent.change(selectors[i], { target: { value: "two" } });
    expect(buttons[i]).toBeEnabled();
    fireEvent.change(selectors[i], { target: { value: "one" } });
    expect(buttons[i]).toBeDisabled();
  }
  expect(run).toHaveBeenCalledTimes(2);
});
it("allows retry after failure", async () => {
  run.mockResolvedValue({ ok: false });
  render(<CourseSharing id="course" teacher="teacher" published />);
  fireEvent.change(screen.getAllByRole("combobox")[0], {
    target: { value: "one" },
  });
  const button = screen.getAllByRole("button", { name: "Назначить" })[0];
  fireEvent.click(button);
  await waitFor(() => expect(run).toHaveBeenCalledTimes(1));
  expect(button).toBeEnabled();
});

it("shows persisted recipients after remount and disables their assignment", () => {
  query.mockImplementation(({ queryKey }: { queryKey: string[] }) => ({
    data: {
      count: 1,
      results: [
        {
          id: "saved",
          recipient_id: "one",
          name: queryKey[2] === "students" ? "Saved student" : "Saved group",
          status: "ACTIVE",
          version_number: 1,
        },
      ],
      selected_assigned: queryKey[4] === "one",
    },
  }));
  const mounted = render(
    <CourseSharing id="course" teacher="teacher" published />,
  );
  expect(screen.getByText("Saved student")).toBeInTheDocument();
  expect(screen.getByText("Saved group")).toBeInTheDocument();
  mounted.unmount();
  render(<CourseSharing id="course" teacher="teacher" published />);
  expect(screen.getByText("Saved student")).toBeInTheDocument();
  const selectors = screen.getAllByRole("combobox");
  const buttons = screen.getAllByRole("button", { name: "Назначить" });
  for (const i of [0, 1]) {
    fireEvent.change(selectors[i], { target: { value: "one" } });
    expect(buttons[i]).toBeDisabled();
    fireEvent.change(selectors[i], { target: { value: "two" } });
    expect(buttons[i]).toBeEnabled();
  }
});

it("requires confirmation before removing a group assignment", async () => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
  query.mockImplementation(({ queryKey }: { queryKey: string[] }) => ({
    data: {
      count: queryKey[2] === "groups" ? 1 : 0,
      results:
        queryKey[2] === "groups"
          ? [
              {
                id: "a1",
                recipient_id: "group-one",
                name: "Group One",
                status: "ACTIVE",
                version_number: 1,
              },
            ]
          : [],
      selected_assigned: false,
    },
  }));
  run.mockResolvedValue({ ok: true });
  render(<CourseSharing id="course" teacher="teacher" published />);
  fireEvent.click(screen.getByRole("button", { name: "Снять назначение" }));
  expect(screen.getByRole("dialog")).toHaveTextContent("Group One");
  expect(run).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Отмена" }));
  expect(run).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Снять назначение" }));
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "Снять назначение",
    }),
  );
  await waitFor(() =>
    expect(run).toHaveBeenCalledWith("groups/group-one/unassign-course/", {
      course: "course",
    }),
  );
});
