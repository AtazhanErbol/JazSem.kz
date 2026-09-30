import type { Page, Row } from "../entities/types";
import i18n from "../i18n";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public fieldErrors: Record<string, string> = {},
  ) {
    super(message);
  }
}
let csrf = "";
async function request(url: string, options: RequestInit) {
  try {
    return await fetch(url, options);
  } catch {
    throw new ApiError(0, i18n.t("networkError"));
  }
}
function errorMessages(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(errorMessages);
  if (value && typeof value === "object")
    return Object.values(value).flatMap(errorMessages);
  return [];
}
async function readResponse(response: Response) {
  if (!response.headers.get("content-type")?.includes("application/json"))
    throw new ApiError(response.status, i18n.t("serviceUnavailable"));
  const data = await response.json();
  if (!response.ok) {
    const details = errorMessages(data.errors);
    throw new ApiError(
      response.status,
      [
        ...new Set(
          details.length
            ? details
            : [data.message || i18n.t("serviceUnavailable")],
        ),
      ].join(" "),
      data.errors &&
        typeof data.errors === "object" &&
        !Array.isArray(data.errors)
        ? Object.fromEntries(
            Object.entries(data.errors).map(([field, value]) => [
              field,
              errorMessages(value).join(" "),
            ]),
          )
        : {},
    );
  }
  return data;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  if (method !== "GET" && !csrf) {
    const response = await request("/api/v1/auth/login/", {
      credentials: "same-origin",
    });
    csrf = ((await readResponse(response)) as { csrfToken: string }).csrfToken;
  }
  const form = body instanceof FormData;
  const response = await request("/api/v1/" + path, {
    method,
    credentials: "same-origin",
    headers: {
      "Accept-Language": i18n.language || "ru",
      ...(form ? {} : { "Content-Type": "application/json" }),
      ...(method !== "GET" ? { "X-CSRFToken": csrf } : {}),
    },
    body: body === undefined ? undefined : form ? body : JSON.stringify(body),
  });
  if (path.startsWith("auth/") && method === "POST" && response.ok) csrf = "";
  if (response.status === 204) return undefined as T;
  return (await readResponse(response)) as T;
}
export async function allRows(path: string): Promise<Row[]> {
  const result: Row[] = [];
  let next: string | null = path;
  while (next) {
    const page: Page<Row> = await api<Page<Row>>(next);
    result.push(...page.results);
    next = page.next ? page.next.split("/api/v1/")[1] : null;
  }
  return result;
}
