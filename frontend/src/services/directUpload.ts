const routes =
  /^(materials\/|materials\/[0-9a-f-]{36}\/|sources\/|assignments\/[0-9a-f-]{36}\/submit\/)$/i;
const types: Record<string, string> = {
  pdf: "application/pdf",
  txt: "text/plain",
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  doc: "application/msword",
  ppt: "application/vnd.ms-powerpoint",
  xls: "application/vnd.ms-excel",
  csv: "text/csv",
  webp: "image/webp",
  gif: "image/gif",
  mp4: "video/mp4",
  webm: "video/webm",
  odt: "application/vnd.oasis.opendocument.text",
  odp: "application/vnd.oasis.opendocument.presentation",
  ods: "application/vnd.oasis.opendocument.spreadsheet",
};

type Grant = { ticket: string; url: string; fields: Record<string, string> };
type Prepare = (body: unknown) => Promise<{ uploads: Grant[] }>;

export function usesDirectUpload(
  path: string,
  body: unknown,
): body is FormData {
  return (
    import.meta.env.VITE_DIRECT_UPLOADS === "true" &&
    routes.test(path) &&
    body instanceof FormData &&
    Array.from(body.values()).some((value) => value instanceof File)
  );
}

export async function directUpload(
  target: string,
  method: string,
  form: FormData,
  prepare: Prepare,
  signal?: AbortSignal,
  onProgress?: (percent: number) => void,
) {
  const data: Record<string, string> = {};
  const files: { field: string; file: File }[] = [];
  for (const [field, value] of form.entries()) {
    if (value instanceof File) files.push({ field, file: value });
    else data[field] = value;
  }
  signal?.throwIfAborted();
  const result = await prepare({
    target,
    method,
    data,
    files: files.map(({ field, file }) => ({
      field,
      name: file.name,
      type:
        file.type ||
        types[file.name.split(".").pop()?.toLowerCase() || ""] ||
        "",
      size: file.size,
    })),
  });
  if (result.uploads.length !== files.length)
    throw new Error("Invalid upload grants");
  for (let i = 0; i < files.length; i++) {
    signal?.throwIfAborted();
    const grant = result.uploads[i];
    const url = new URL(grant.url);
    if (url.protocol !== "https:")
      throw new Error("Insecure upload destination");
    const payload = new FormData();
    Object.entries(grant.fields).forEach(([key, value]) =>
      payload.append(key, value),
    );
    // S3 POST requires the file to be the final multipart field.
    payload.append("file", files[i].file);
    if (onProgress) {
      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        const abort = () => xhr.abort();
        const finish = () => signal?.removeEventListener("abort", abort);
        xhr.open("POST", url);
        xhr.withCredentials = false;
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable)
            onProgress(Math.round((event.loaded / event.total) * 100));
        };
        xhr.onload = () => {
          finish();
          if (xhr.status >= 200 && xhr.status < 300) resolve();
          else reject(new Error("Private upload failed"));
        };
        xhr.onerror = () => {
          finish();
          reject(new Error("Private upload failed"));
        };
        xhr.onabort = () => {
          finish();
          reject(new DOMException("Upload cancelled", "AbortError"));
        };
        signal?.addEventListener("abort", abort, { once: true });
        if (signal?.aborted) {
          finish();
          reject(new DOMException("Upload cancelled", "AbortError"));
          return;
        }
        xhr.send(payload);
      });
      continue;
    }
    const response = await fetch(url, {
      method: "POST",
      body: payload,
      credentials: "omit",
      referrerPolicy: "no-referrer",
      signal,
    });
    if (!response.ok) throw new Error("Private upload failed");
  }
  return { data, tickets: result.uploads.map(({ ticket }) => ticket) };
}
