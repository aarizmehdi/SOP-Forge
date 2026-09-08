export type Role = "employee" | "manager" | "executive" | "admin";
export type RequestType = "leave" | "reimbursement" | "it_access" | "other";
export type Decision = "approved" | "rejected" | "routed" | "pending";
export type RequestStatus =
  "in_progress" | "escalated" | "resolved" | "overridden";
export type ConversationDomain =
  "leave_hr" | "expenses_finance" | "it_system_access" | "policies_general";
export type ConversationLanguage = "en" | "roman_urdu";
export type ConversationUIState =
  | "DOMAIN_SELECTION"
  | "LANGUAGE_SELECTION"
  | "ACTIVE_CHAT"
  | "EVIDENCE_GATE"
  | "TERMINAL";
export type AllowedAction =
  | "send_message"
  | "use_microphone"
  | "upload_evidence"
  | "skip_evidence"
  | "view_request"
  | "start_new_conversation";
export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  role: Role;
  employee_id: string;
  name: string;
}
export interface UserProfile {
  id: string;
  employee_id: string;
  name: string;
  email: string;
  role: Role;
  department_name: string | null;
  is_active: boolean;
}
export interface Evidence {
  id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
}
export interface EvidenceUploadResponse {
  status: string;
  message: string;
  evidence: Evidence;
  new_request_status: RequestStatus;
  new_decision: Decision;
}
export interface RequestItem {
  id: string;
  request_type: RequestType;
  decision: Decision;
  status: RequestStatus;
  confidence: number | null;
  has_evidence: boolean;
  evidence_list: Evidence[];
  created_at: string;
}
export interface RequestDetail extends RequestItem {
  employee_id: string;
  submitted_data: Record<string, unknown>;
  evaluation_reasoning: string | null;
  retrieved_policy_refs: string[] | null;
  sla_deadline: string | null;
  override_log: Record<string, unknown>[] | null;
  updated_at: string;
}
export interface TerminalResult {
  outcome: "request_result" | "incomplete_conversation";
  request_id?: string;
  status?: RequestStatus;
  decision?: Decision;
  destination?: "manager_review" | "human_review";
  missing_concept?: string;
}
export interface AssistantResponse {
  response_type:
    "chat" | "request_processed" | "policy_info" | "conversation_incomplete";
  message: string;
  request_details?: RequestDetail | null;
  conversation_id?: string | null;
  draft_state?: string | null;
  upload_available: boolean;
  retrieval_mode?: string | null;
  ui_state: ConversationUIState;
  allowed_actions: AllowedAction[];
  terminal?: TerminalResult | null;
}
export interface ReviewItem {
  id: string;
  employee_name: string;
  employee_id_code: string;
  department: string | null;
  request_type: RequestType;
  submitted_data: Record<string, unknown>;
  ai_decision: Decision;
  ai_confidence: number | null;
  evaluation_reasoning: string | null;
  policy_refs: string[] | null;
  status: RequestStatus;
  sla_deadline: string | null;
  sla_remaining_minutes: number | null;
  override_log: Record<string, unknown>[] | null;
  has_evidence: boolean;
  evidence_list: Evidence[] | null;
  created_at: string;
}
export interface AuditLog {
  id: string;
  request_id: string | null;
  event_type: string;
  actor_id: string | null;
  actor_name: string | null;
  actor_role: string | null;
  decision: string | null;
  confidence: number | null;
  policy_refs: string[] | null;
  evaluation_reasoning: string | null;
  override_justification: string | null;
  previous_decision: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}
export interface AuditSummary {
  total_entries: number;
  auto_approved: number;
  auto_rejected: number;
  escalated: number;
  overridden: number;
  sla_breaches: number;
}
export interface Incident {
  id: string;
  employee_id: string;
  incident_type: string;
  message: string;
  ai_reasoning: string | null;
  status: "open" | "reviewed";
  confidence: number;
  conversation_id: string | null;
  created_at: string;
}
export interface SopDocumentListItem {
  id: string;
  title: string;
  category: string;
  version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
export interface SopDocument extends SopDocumentListItem {
  content_text: string;
  chunk_count: number | null;
}
export interface SopChunk {
  id: string;
  chunk_text: string;
  chunk_index: number;
  has_embedding: boolean;
  metadata: Record<string, unknown> | null;
}
export interface Health {
  status: string;
  service: string;
  version: string;
  llm_configured: boolean;
  redis_connected: boolean;
}
