import { afterEach, describe, expect, it, vi } from "vitest";

import { directUpload, usesDirectUpload } from "./directUpload";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("private direct uploads", () => {
  it("reports storage progress without sending session credentials or file bytes to Django", async () => {
    const sent: { credentials: boolean; url: string; body: FormData }[] = [];
    class StorageRequest {
      withCredentials = true;
      status = 204;
      url = "";
      upload: {
        onprogress?: (event: {
          lengthComputable: boolean;
          loaded: number;
          total: number;
        }) => void;
      } = {};
      onload?: () => void;
      onerror?: () => void;
      onabort?: () => void;
      open(_method: string, url: URL) {
        this.url = String(url);
      }
      send(body: FormData) {
        sent.push({ credentials: this.withCredentials, url: this.url, body });
        this.upload.onprogress?.({
          lengthComputable: true,
          loaded: 50,
          total: 100,
        });
        this.onload?.();
      }
      abort() {
        this.onabort?.();
      }
    }
    vi.stubGlobal("XMLHttpRequest", StorageRequest);
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const prepare = vi.fn().mockResolvedValue({
      uploads: [
        {
          ticket: "ticket",
          url: "https://storage.example.test/",
          fields: { key: "private/quarantine/test" },
        },
      ],
    });
    const form = new FormData();
    form.append("kind", "VIDEO");
    form.append(
      "file",
      new File(["video bytes"], "video.mp4", { type: "video/mp4" }),
    );
    const progress = vi.fn();
    const result = await directUpload(
      "attachments/",
      "POST",
      form,
      prepare,
      undefined,
      progress,
    );
    expect(progress).toHaveBeenCalledWith(50);
    expect(sent[0].credentials).toBe(false);
    expect(sent[0].url).toBe("https://storage.example.test/");
    expect(result).toEqual({ data: { kind: "VIDEO" }, tickets: ["ticket"] });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("aborts an in-flight storage transfer before finalization", async () => {
    let aborted = false;
    class StorageRequest {
      withCredentials = true;
      upload = {};
      status = 0;
      onabort?: () => void;
      open() {}
      send() {}
      abort() {
        aborted = true;
        this.onabort?.();
      }
    }
    vi.stubGlobal("XMLHttpRequest", StorageRequest);
    const form = new FormData();
    form.append("file", new File(["video"], "video.webm"));
    const prepare = vi.fn().mockResolvedValue({
      uploads: [
        {
          ticket: "ticket",
          url: "https://storage.example.test/",
          fields: {},
        },
      ],
    });
    const controller = new AbortController();
    const pending = directUpload(
      "attachments/",
      "POST",
      form,
      prepare,
      controller.signal,
      vi.fn(),
    );
    await Promise.resolve();
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
    expect(aborted).toBe(true);
  });
  it("sends a 25 MiB file only to storage, with no session credentials", async () => {
    const file = new File([new Uint8Array(25 * 1024 * 1024)], "notes.txt", {
      type: "text/plain",
    });
    const form = new FormData();
    form.append("title", "Material");
    form.append("file", file);
    const prepare = vi.fn().mockResolvedValue({
      uploads: [
        {
          ticket: "one-time-ticket",
          url: "https://storage.example.test/bucket",
          fields: { policy: "signed-policy", key: "private/quarantine/random" },
        },
      ],
    });
    const fetch = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetch);
    const result = await directUpload("materials/", "POST", form, prepare);
    expect(prepare).toHaveBeenCalledWith({
      target: "materials/",
      method: "POST",
      data: { title: "Material" },
      files: [
        {
          field: "file",
          name: "notes.txt",
          type: "text/plain",
          size: 25 * 1024 * 1024,
        },
      ],
    });
    const [url, options] = fetch.mock.calls[0];
    expect(url.href).toBe("https://storage.example.test/bucket");
    expect(options.credentials).toBe("omit");
    expect(options.headers).toBeUndefined();
    expect(Array.from((options.body as FormData).keys())).toEqual([
      "policy",
      "key",
      "file",
    ]);
    expect((options.body as FormData).get("file")).toBe(file);
    expect(result).toEqual({
      data: { title: "Material" },
      tickets: ["one-time-ticket"],
    });
    expect(JSON.stringify(result)).not.toContain("signed-policy");
  });

  it("preserves all five submission files and their order", async () => {
    const form = new FormData();
    for (let n = 0; n < 5; n++)
      form.append("files", new File([String(n)], `${n}.txt`));
    const prepare = vi.fn().mockResolvedValue({
      uploads: Array.from({ length: 5 }, (_, n) => ({
        ticket: String(n),
        url: "https://storage.example.test/",
        fields: {},
      })),
    });
    const fetch = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetch);
    const result = await directUpload(
      "assignments/id/submit/",
      "POST",
      form,
      prepare,
    );
    expect(fetch).toHaveBeenCalledTimes(5);
    expect(result.tickets).toEqual(["0", "1", "2", "3", "4"]);
    expect(
      prepare.mock.calls[0][0].files.every(
        (f: { type: string }) => f.type === "text/plain",
      ),
    ).toBe(true);
  });

  it("never attaches files after a failed or cancelled storage upload", async () => {
    const form = new FormData();
    form.append("file", new File(["test"], "test.txt"));
    const prepare = vi.fn().mockResolvedValue({
      uploads: [
        {
          ticket: "ticket",
          url: "https://storage.example.test/",
          fields: {},
        },
      ],
    });
    const fetch = vi.fn().mockResolvedValue({ ok: false });
    vi.stubGlobal("fetch", fetch);
    await expect(
      directUpload("materials/", "POST", form, prepare),
    ).rejects.toThrow();
    const controller = new AbortController();
    controller.abort();
    await expect(
      directUpload("materials/", "POST", form, prepare, controller.signal),
    ).rejects.toThrow();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("preserves ordinary multipart imports and local development", () => {
    const form = new FormData();
    form.append("file", new File(["test"], "test.txt"));
    expect(usesDirectUpload("materials/", form)).toBe(false);
    vi.stubEnv("VITE_DIRECT_UPLOADS", "true");
    expect(usesDirectUpload("materials/", form)).toBe(true);
    expect(usesDirectUpload("users/import/", form)).toBe(false);
    expect(usesDirectUpload("tests/id/import/", form)).toBe(false);
    expect(usesDirectUpload("materials/", { title: "Text only" })).toBe(false);
  });
});
