const API_BASE = process.env.API_URL ?? "http://127.0.0.1:8000";

export type ApiUser = {
  id: string;
  email: string;
  created_at: string;
};

export type ApiFieldError = { field: string; message: string };

/**
 * A failure we can show a person. `status` is the API's own status code, or 0
 * when the API could not be reached at all.
 */
export class ApiError extends Error {
  status: number;
  fields: ApiFieldError[];

  constructor(status: number, message: string, fields: ApiFieldError[] = []) {
    super(message);
    this.status = status;
    this.fields = fields;
  }
}

/**
 * Turn FastAPI's error body into something a person can act on.
 * 422 bodies are `{detail: [{loc: ["body", "email"], msg: "..."}]}`;
 * everything else is `{detail: "..."}`.
 */
function toError(status: number, body: unknown): ApiError {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;

    if (typeof detail === "string") {
      return new ApiError(status, detail);
    }

    if (Array.isArray(detail)) {
      const fields = detail.flatMap((item) => {
        if (typeof item !== "object" || item === null) return [];
        const { loc, msg } = item as { loc?: unknown; msg?: unknown };
        const field = Array.isArray(loc) ? String(loc.at(-1)) : "";
        return typeof msg === "string" ? [{ field, message: msg }] : [];
      });
      return new ApiError(status, "Some details need fixing.", fields);
    }
  }

  return new ApiError(status, "Something went wrong. Try again.");
}

async function request<T>(
  path: string,
  init: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, ...rest } = init;
  const headers = new Headers(rest.headers);
  headers.set("Accept", "application/json");
  if (rest.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...rest,
      headers,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      0,
      "Can't reach the API. Is it running on port 8000?",
    );
  }

  if (response.status === 204) return undefined as T;

  const body = await response.json().catch(() => null);
  if (!response.ok) throw toError(response.status, body);
  return body as T;
}

export function signup(email: string, password: string) {
  return request<{ access_token: string; token_type: string; user: ApiUser }>(
    "/api/v1/auth/signup",
    { method: "POST", body: JSON.stringify({ email, password }) },
  );
}

export function login(email: string, password: string) {
  return request<{ access_token: string; token_type: string }>(
    "/api/v1/auth/login",
    { method: "POST", body: JSON.stringify({ email, password }) },
  );
}

export function getMe(token: string) {
  return request<ApiUser>("/api/v1/users/me", { token });
}
