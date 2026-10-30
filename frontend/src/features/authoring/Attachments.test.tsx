import {
  fireEvent,
  render,
  screen,
  waitFor,
  act,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import "../../i18n";
import { api } from "../../services/api";
import { Attachments } from "./Attachments";

vi.mock("../../services/api", async (original) => ({
  ...(await original<typeof import("../../services/api")>()),
  api: vi.fn(),
}));

it("refreshes a committed upload even when the initial list snapshot is still pending", async () => {
  const empty = { count: 0, next: null, previous: null, results: [] };
  let finishInitial: (value: typeof empty) => void = () => undefined;
  let listed = 0;
  const attachment = {
    id: "resource-1",
    title: "New resource",
    description: "",
    kind: "FILE",
    original_filename: "notes.txt",
    mime_type: "text/plain",
    file: true,
    size: 5,
    order: 0,
    created_at: "2026-10-30T00:00:00Z",
    uploaded_at: "2026-10-30T00:00:00Z",
  };
  vi.mocked(api).mockImplementation(async (path, method) => {
    if (path === "attachments/config/")
      return {
        document_types: { ".txt": "text/plain" },
        video_types: {},
        max_document_bytes: 1024,
        max_video_bytes: 1024,
        direct_uploads: false,
      };
    if (method === "POST") return attachment;
    if (path.startsWith("attachments/?")) {
      listed += 1;
      if (listed === 1)
        return new Promise<typeof empty>((resolve) => {
          finishInitial = resolve;
        });
      return { ...empty, count: 1, results: [attachment] };
    }
    throw new Error(`Unexpected request ${path}`);
  });
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const view = render(
    <QueryClientProvider client={cache}>
      <Attachments owner="assignment" ownerId="assignment-1" editable />
    </QueryClientProvider>,
  );
  await waitFor(() =>
    expect(view.container.querySelector('input[type="file"]')).toBeTruthy(),
  );
  fireEvent.change(view.container.querySelector('input[type="file"]')!, {
    target: {
      files: [new File(["notes"], "notes.txt", { type: "text/plain" })],
    },
  });
  expect(await screen.findByText("New resource")).toBeTruthy();
  await act(async () => {
    finishInitial(empty);
  });
  expect(screen.getByText("New resource")).toBeTruthy();
  expect(listed).toBe(2);
  cache.clear();
});
