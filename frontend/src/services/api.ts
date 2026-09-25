import type { Page, Row } from "../entities/types";
import i18n from "../i18n";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
let csrf = "";
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  if (method !== "GET" && !csrf) {
    const response = await fetch("/api/v1/auth/login/", {
      credentials: "same-origin",
    });
    csrf = ((await response.json()) as { csrfToken: string }).csrfToken;
  }
  const form = body instanceof FormData;
  const response = await fetch("/api/v1/" + path, {
    method,
    credentials: "same-origin",
    headers: {
      "Accept-Language": i18n.language || "ru",
      ...(form ? {} : { "Content-Type": "application/json" }),
      ...(method !== "GET" ? { "X-CSRFToken": csrf } : {}),
    },
    body: body === undefined ? undefined : form ? body : JSON.stringify(body),
  });
  if (path === "auth/login/" && method === "POST" && response.ok) csrf = "";
  if (response.status === 204) return undefined as T;
  if (!response.headers.get("content-type")?.includes("application/json"))
    throw new ApiError(
      response.status,
      "Сервис временно недоступен. Повторите позже.",
    );
  const data = await response.json();
  if (!response.ok)
    throw new ApiError(
      response.status,
      data.message + (data.errors ? " " + JSON.stringify(data.errors) : ""),
    );
  return data as T;
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
