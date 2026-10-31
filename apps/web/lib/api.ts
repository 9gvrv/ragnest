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
  // FormData must keep the browser/undici-generated multipart boundary.
  if (rest.body && !(rest.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
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

export type ApiRole = "creator" | "admin" | "member";

export type ApiWorkspace = {
  id: string;
  name: string;
  created_by: string;
  created_at: string;
};

export type ApiMember = {
  user_id: string;
  email: string;
  role: ApiRole;
  joined_at: string;
};

export type ApiDocument = {
  id: string;
  workspace_id: string;
  uploaded_by: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  page_count: number | null;
  char_count: number;
  created_at: string;
};

export type ApiDocumentDetail = ApiDocument & {
  extracted_text: string;
};

export type ApiPendingInvitation = {
  invitation_id: string;
  workspace_id: string;
  workspace_name: string;
  inviter_email: string | null;
  email: string;
  role: ApiRole;
  token: string;
  expires_at: string;
  created_at: string;
};

/**
 * The public preview carries the same facts as a pending row minus the token
 * (the page already has it from the URL), plus the invitation's status.
 */
export type ApiInvitationPreview = Omit<ApiPendingInvitation, "token"> & {
  status: "pending" | "accepted" | "declined" | "expired";
};

export type ApiInvitationCreated = {
  exists: boolean;
  invitation_id: string | null;
  email: string;
  role: ApiRole;
  token: string | null;
  expires_at: string | null;
  link: string | null;
  message?: string | null;
};

export type ApiAcceptedInvitation = {
  workspace_id: string;
  role: ApiRole;
  workspace_name: string;
};

export function listWorkspaces(token: string) {
  return request<ApiWorkspace[]>("/api/v1/workspaces", { token });
}

export function createWorkspace(token: string, name: string) {
  return request<ApiWorkspace>("/api/v1/workspaces", {
    method: "POST",
    body: JSON.stringify({ name }),
    token,
  });
}

export function getWorkspace(token: string, workspaceId: string) {
  return request<ApiWorkspace>(`/api/v1/workspaces/${workspaceId}`, { token });
}

export function deleteWorkspace(token: string, workspaceId: string) {
  return request<void>(`/api/v1/workspaces/${workspaceId}`, {
    method: "DELETE",
    token,
  });
}

export function listMembers(token: string, workspaceId: string) {
  return request<ApiMember[]>(`/api/v1/workspaces/${workspaceId}/members`, {
    token,
  });
}

export function removeMember(
  token: string,
  workspaceId: string,
  userId: string,
) {
  return request<void>(
    `/api/v1/workspaces/${workspaceId}/members/${userId}`,
    { method: "DELETE", token },
  );
}

export function listDocuments(
  token: string,
  workspaceId: string,
  mine = false,
) {
  const query = mine ? "?mine=true" : "";
  return request<ApiDocument[]>(
    `/api/v1/workspaces/${workspaceId}/documents${query}`,
    { token },
  );
}

export function getDocument(
  token: string,
  workspaceId: string,
  documentId: string,
) {
  return request<ApiDocumentDetail>(
    `/api/v1/workspaces/${workspaceId}/documents/${documentId}`,
    { token },
  );
}

/**
 * Multipart upload. The `FormData` is passed through untouched so the fetch
 * implementation sets the boundary; never set `Content-Type` by hand here.
 */
export function uploadDocument(
  token: string,
  workspaceId: string,
  file: File,
) {
  const body = new FormData();
  body.set("file", file);
  return request<ApiDocument>(`/api/v1/workspaces/${workspaceId}/documents`, {
    method: "POST",
    body,
    token,
  });
}

export function deleteDocument(
  token: string,
  workspaceId: string,
  documentId: string,
) {
  return request<void>(
    `/api/v1/workspaces/${workspaceId}/documents/${documentId}`,
    { method: "DELETE", token },
  );
}

export function checkInvitationEmail(
  token: string,
  workspaceId: string,
  email: string,
) {
  return request<{ exists: boolean; user_id: string | null }>(
    `/api/v1/workspaces/${workspaceId}/invitations/check`,
    { method: "POST", body: JSON.stringify({ email }), token },
  );
}

export function createInvitation(
  token: string,
  workspaceId: string,
  email: string,
  role: string,
) {
  return request<ApiInvitationCreated>(
    `/api/v1/workspaces/${workspaceId}/invitations`,
    { method: "POST", body: JSON.stringify({ email, role }), token },
  );
}

/** Public: no session token, the invitation token is the capability. */
export function getInvitationPreview(invitationToken: string) {
  return request<ApiInvitationPreview>(
    `/api/v1/invitations/${encodeURIComponent(invitationToken)}`,
  );
}

export function listPendingInvitations(token: string) {
  return request<ApiPendingInvitation[]>("/api/v1/invitations/pending", {
    token,
  });
}

export function acceptInvitation(token: string, invitationToken: string) {
  return request<ApiAcceptedInvitation>(
    `/api/v1/invitations/${encodeURIComponent(invitationToken)}/accept`,
    { method: "POST", token },
  );
}

export function declineInvitation(token: string, invitationToken: string) {
  return request<void>(
    `/api/v1/invitations/${encodeURIComponent(invitationToken)}/decline`,
    { method: "POST", token },
  );
}

/**
 * Build the route-handler response for a caught API failure: the API's status
 * (0 means unreachable, which becomes 502) and the `{detail, fields}` body the
 * client components already know how to read.
 */
export function apiErrorResponse(error: unknown): Response {
  if (error instanceof ApiError) {
    return Response.json(
      { detail: error.message, fields: error.fields },
      { status: error.status === 0 ? 502 : error.status },
    );
  }
  return Response.json(
    { detail: "Something went wrong. Try again." },
    { status: 500 },
  );
}
