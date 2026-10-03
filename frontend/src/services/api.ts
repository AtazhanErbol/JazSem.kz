import i18n from "../i18n";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public fieldErrors: Record<string, string> = {},
    public code = "",
  ) {
    super(message);
  }
}
let csrf = "";
let csrfRequest: Promise<string> | undefined;

function csrfCookie() {
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith("csrftoken="));
  return cookie?.slice("csrftoken=".length) || "";
}

async function csrfToken(refresh = false): Promise<string> {
  // Login in another tab (or a local app on another port) can rotate the cookie.
  // Read it for every mutation instead of retaining an old in-memory token.
  if (!refresh) {
    const cookie = csrfCookie();
    if (cookie) return cookie;
    if (csrf) return csrf;
  }
  if (!csrfRequest) {
    const pending = request("/api/v1/auth/login/", {
      credentials: "same-origin",
      cache: "no-store",
    })
      .then(readResponse)
      .then((data: { csrfToken: string }) => data.csrfToken);
    csrfRequest = pending;
    // Share initialization between concurrent actions. An earlier request must
    // not repopulate the cache after a successful auth action invalidates it.
    void pending.then(
      (token) => {
        if (csrfRequest === pending) {
          csrf = token;
          csrfRequest = undefined;
        }
      },
      () => {
        if (csrfRequest === pending) csrfRequest = undefined;
      },
    );
  }
  return csrfRequest;
}
async function request(url: string, options: RequestInit) {
  try {
    return await fetch(url, options);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
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
      typeof data.code === "string" ? data.code : "",
    );
  }
  return data;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  method = method.toUpperCase();
  const mutation = !["GET", "HEAD", "OPTIONS"].includes(method);
  signal?.throwIfAborted();
  const form = body instanceof FormData;
  for (let attempt = 0; ; attempt++) {
    const token = mutation ? await csrfToken(attempt > 0) : "";
    signal?.throwIfAborted();
    const response = await request("/api/v1/" + path, {
      signal,
      method,
      credentials: "same-origin",
      headers: {
        "Accept-Language": i18n.language || "ru",
        ...(form ? {} : { "Content-Type": "application/json" }),
        ...(mutation ? { "X-CSRFToken": token } : {}),
      },
      body: body === undefined ? undefined : form ? body : JSON.stringify(body),
    });
    if (path.startsWith("auth/") && mutation && response.ok) {
      csrf = "";
      csrfRequest = undefined;
    }
    if (response.status === 204) return undefined as T;
    try {
      return (await readResponse(response)) as T;
    } catch (error) {
      // Only this explicit 403 proves the action was rejected before execution.
      // Never replay network failures, permission errors or completed actions.
      if (
        mutation &&
        attempt === 0 &&
        error instanceof ApiError &&
        error.status === 403 &&
        error.code === "csrf_failed"
      ) {
        csrf = "";
        continue;
      }
      throw error;
    }
  }
}
