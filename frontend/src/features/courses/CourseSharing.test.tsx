import { beforeEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
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
