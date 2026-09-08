import type {
  AssistantResponse,
  AuditLog,
  AuditSummary,
  ConversationDomain,
  ConversationLanguage,
  Evidence,
  EvidenceUploadResponse,
  Health,
  Incident,
  LoginResponse,
  RequestDetail,
  RequestItem,
  ReviewItem,
  SopChunk,
  SopDocument,
  SopDocumentListItem,
  UserProfile,
} from "../types/api";
const TOKEN_KEY = "sopforge_token";
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
let unauthorizedHandler: (() => void) | null = null;
export const setUnauthorizedHandler = (handler: (() => void) | null) => {
  unauthorizedHandler = handler;
};
export const getStoredToken = () => localStorage.getItem(TOKEN_KEY);
function errorMessage(body: unknown, fallback: string) {
  if (!body || typeof body !== "object") return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail)
    return String((detail as { message: unknown }).message);
  return fallback;
}
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getStoredToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiError(
      "Cannot connect to SOP Forge. Check that the service is running.",
      0,
      "network_error",
    );
  }
  if (response.status === 401) unauthorizedHandler?.();
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail =
      body && typeof body === "object"
        ? (body as { detail?: unknown }).detail
        : undefined;
    const code =
      detail && typeof detail === "object" && "code" in detail
        ? String((detail as { code: unknown }).code)
        : undefined;
    throw new ApiError(
      errorMessage(body, `Request failed (${response.status})`),
      response.status,
      code,
      detail,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });
export const api = {
  login: (email: string, password: string) =>
    request<LoginResponse>("/api/auth/login", {
      method: "POST",
      ...json({ email, password }),
    }),
  profile: () => request<UserProfile>("/api/auth/me"),
  startConversation: (
    domain: ConversationDomain,
    language: ConversationLanguage,
  ) =>
    request<AssistantResponse>("/api/request/assistant/start", {
      method: "POST",
      ...json({ domain, language }),
    }),
  chat: (message: string, conversation_id: string) =>
    request<AssistantResponse>("/api/request/assistant", {
      method: "POST",
      ...json({ message, conversation_id }),
    }),
  uploadDraftEvidence: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<AssistantResponse>(`/api/evidence/draft/${id}`, {
      method: "POST",
      body: form,
    });
  },
  skipDraftEvidence: (id: string) =>
    request<AssistantResponse>(`/api/evidence/draft/${id}/skip`, {
      method: "POST",
    }),
  requests: (limit = 50, offset = 0) =>
    request<RequestItem[]>(`/api/request/my?limit=${limit}&offset=${offset}`),
  request: (id: string) => request<RequestDetail>(`/api/request/${id}`),
  uploadRequestEvidence: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<EvidenceUploadResponse>(
      `/api/evidence/upload/${encodeURIComponent(id)}`,
      {
        method: "POST",
        body: form,
      },
    );
  },
  leaveBalances: () =>
    request<Record<string, unknown>>("/api/request/leave-balances"),
  submitRequest: (payload: {
    request_type: string;
    submitted_data: Record<string, unknown>;
  }) =>
    request<RequestDetail>("/api/request/submit", {
      method: "POST",
      ...json(payload),
    }),
  reviewQueue: (
    status: "escalated" | "resolved" | "past" | "all" = "escalated",
  ) =>
    request<ReviewItem[]>(
      `/api/review/pending?status_filter=${encodeURIComponent(status)}`,
    ),
  decide: (id: string, decision: string, comment: string) =>
    request<{ status: string; message: string }>(`/api/review/${id}/decide`, {
      method: "POST",
      ...json({ decision, comment }),
    }),
  override: (id: string, new_decision: string, justification: string) =>
    request<{ status: string; message: string }>(`/api/review/${id}/override`, {
      method: "POST",
      ...json({ new_decision, justification }),
    }),
  openEvidence: async (id: string) => {
    const popup = window.open("about:blank", "_blank", "noopener,noreferrer");
    if (popup) popup.opener = null;
    try {
      const headers = new Headers();
      const token = getStoredToken();
      if (token) headers.set("Authorization", `Bearer ${token}`);
      const response = await fetch(`/api/evidence/file/${id}`, { headers });
      if (response.status === 401) unauthorizedHandler?.();
      if (!response.ok) {
        const body: unknown = await response.json().catch(() => null);
        throw new ApiError(
          errorMessage(body, "Unable to open evidence."),
          response.status,
        );
      }
      const url = URL.createObjectURL(await response.blob());
      if (popup) popup.location.href = url;
      else {
        const link = document.createElement("a");
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.click();
      }
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (error) {
      popup?.close();
      throw error;
    }
  },
  audits: (params: Record<string, string | number> = {}) =>
    request<AuditLog[]>(
      `/api/audit/logs?${new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString()}`,
    ),
  auditSummary: () => request<AuditSummary>("/api/audit/summary"),
  incidents: () => request<Incident[]>("/api/incidents"),
  dismissIncident: (id: string) =>
    request<Incident>(`/api/incidents/${id}/dismiss`, { method: "PUT" }),
  policies: (activeOnly = false) =>
    request<SopDocumentListItem[]>(`/api/admin/sop?active_only=${activeOnly}`),
  policy: (id: string) => request<SopDocument>(`/api/admin/sop/${id}`),
  createPolicy: (body: {
    title: string;
    category: string;
    content_text: string;
  }) =>
    request<SopDocument>("/api/admin/sop", { method: "POST", ...json(body) }),
  updatePolicy: (
    id: string,
    body: Partial<{ title: string; category: string; content_text: string }>,
  ) =>
    request<SopDocument>(`/api/admin/sop/${id}`, {
      method: "PUT",
      ...json(body),
    }),
  deactivatePolicy: (id: string) =>
    request<{ status: string; message: string }>(`/api/admin/sop/${id}`, {
      method: "DELETE",
    }),
  policyChunks: (id: string) =>
    request<SopChunk[]>(`/api/admin/sop/${id}/chunks`),
  speechToken: () => request<{ token: string }>("/api/speech/token"),
  health: () => request<Health>("/health"),
};
