# SOP Forge Phase 1 runtime architecture

Baseline inspected: `2d47676`, current local main, 2026-09-06. This document derives from source inspection, not prior repository documentation.

## 1. Runtime architecture

Before: vanilla JS chat sends the complete browser transcript to FastAPI `/api/request/assistant`. A DeepSeek call chooses ASK/SUBMIT/ESCALATE; `_set_defaults` invents missing fields. Submission creates MongoDB `sop_requests`, history and audit records and a Redis cache. LangGraph runs intake → policy retrieval → another LLM extraction → Python DMN → confidence routing → auto decision or escalation → audit. Forms submit arbitrary dictionaries to the same graph. Evidence upload reruns the graph. MongoDB stores policies/chunks; Python ranks embeddings.

Target: chat message → candidate interpreter → owned MongoDB draft → deterministic merge/date normalization/schema validation → live preflight → Python planner → normalized submission → existing LangGraph DMN → persisted result → deterministic employee status. Forms converge on the same request-specific normalization. The graph does not reinterpret normalized business fields using another LLM. Policy excerpts inform explanations/review references, never approval rules.

## 2. Conversational request lifecycle

First message creates an employee-owned UUID conversation. Later turns load it by ID and owner, ignoring client history for business state. A revision compare-and-set protects simultaneous turns. A submitted draft links to one stable request ID; retries return that request instead of duplicating it. Completed requests are immutable through chat; a new conversation starts a new request. Drafts collect required information and resolve ambiguity before submission. Policy-only questions never submit or merge hypothetical facts.

## 3. RequestDraft state

`request_drafts`: id/conversation_id, employee_id, request_type, candidate fields, date source tracking, evidence_required, evidence_present, evidence_choice (undecided/upload/continue_without), missing_fields, ambiguous_fields, last_question, preflight decision/reason/policy references, state, language, revision, request_id, created_at, updated_at. Draft states: collecting, awaiting_evidence, attaching_evidence, submitting, submitted. Attaching/submitting are temporary concurrency guards. Ownership comes exclusively from authenticated users. Evidence presence is queried from MongoDB, not accepted from LLM/browser facts. Changes to date, duration or leave category invalidate derived values and recompute evidence requirements. The last server question supplies context for short replies without trusting browser history.

## 4. LLM responsibilities

Interpret English/Roman Urdu and corrections; propose intent, only explicitly known candidate fields, date expressions, language and ambiguities. Never calculate final dates/duration, decide completeness, set workflow actions, balances, permission, evidence existence or approval. No client transcript is supplied as trusted context. One structured extraction per meaningful chat turn; no response-generation LLM controls status. Explicitly limited development parsing is available without a configured model; configured-provider failure asks for retry.

## 5. Deterministic responsibilities

Python validates field families against request type; normalizes supported date expressions using organization-local date; calculates inclusive calendar days; rejects contradictory duration/ranges and multi-day half-days; uses request-specific Pydantic schemas. Unknown business facts remain missing. The planner asks one relevant question, handles evidence choices, answers policy questions or submits. DMN owns balance, blackout, overlap, evidence-review and category/access/expense rules. Sick evidence threshold is configuration shared by planner and DMN (default three days).

Validation first determines whether there is enough data for preflight. Complete drafts fetch live HRMS and policy guidance, run deterministic preflight, then replan; a routed preflight produces ESCALATE_FOR_REVIEW. Both submission actions enter the governed graph, which refreshes authoritative data before final persistence. Clear first-person symptoms can normalize an omitted sick category; relatives' illness cannot. USD markers/commas are normalized as notation without currency conversion. Bare yes/no, no-document statements and negative send instructions cannot authorize evidence omission. Graph confidence is a compatibility field for validated inputs, not model certainty.

## 6. Evidence lifecycle

Complete evidence-required draft → natural preference question. Upload choice → awaiting_evidence draft and functional upload control. File metadata links to draft before submission, then links to final request. Continue-without → final request routed/escalated with missing-evidence reason. Attached evidence also routes for human review: file presence is never verification. Request uploads are allowed only before human finalization and cannot overwrite manager/executive outcomes. Read/list/upload authorization resolves request.employee_id → users.department_id; cross-department managers are denied. Executive/admin review is organization-wide. No OCR, vision or authenticity verification.

## 7. RAG scope

MongoDB SOP documents/chunks plus real OpenAI embeddings and Python cosine similarity remain. No dedicated vector database exists in Phase 1. `PolicyRetrievalAdapter` isolates that implementation and returns a typed `match`, `no_match`, `degraded`, or `error` result. Unavailable embeddings use explicitly degraded keyword retrieval. Legacy untagged/SHA-256 vectors are not assumed semantic; re-ingestion is needed to mark trusted provider vectors. Policy excerpts and retrieval status support guidance, references, diagnostics, and audit. The DMN does not consume retrieval status or policy text, so a normal no-match and a retrieval-provider error do not change deterministic approval semantics. A future vector store replaces the adapter implementation without changing workflow or DMN rules.

## 8. Trust boundaries

Browser: message/ID/file bytes only, authenticated and ownership checked; history never proves approvals. LLM: untrusted allowlisted candidate facts. Server: validated request shape, derived dates, lifecycle and status rendering. HRMS: live profile/balance/overlap, with failures preventing approval. MongoDB: evidence existence and manager decisions. Direct request and evidence reads enforce employee ownership, same-department manager access, and organization-wide executive/admin access. Dynamic employee, policy, audit, incident, and error strings are escaped before entering template HTML; toast messages use `textContent`. Ordinary personal reasons are not HR misconduct; existing explicit incident tooling remains separate.

## 9. Request status state machine

SOPRequest retains valid enums: status in_progress/escalated/resolved/overridden; decision pending/routed/approved/rejected. Submission creates in_progress+pending. DMN pass finalizes resolved+approved; hard rejection finalizes resolved+rejected; exceptions/failures create escalated+routed. Manager decision: escalated → resolved (approved/rejected), or retained escalated+routed for more information. Executive override: eligible submitted state → overridden with approved/rejected decision and audit justification. Evidence collection lives exclusively on drafts, never as an ad-hoc request decision. Workflow writes use status guards so a delayed run cannot overwrite human decisions.

## 10. Failure behavior

Invalid LLM JSON/provider failure: retry without unsafe submission. Corrupt draft: safe error, no overwrite. Concurrent turn: conflict/retry. HRMS unavailable/incomplete: route for review. Retrieval no-match: return explicit no-match guidance and continue deterministic evaluation. Retrieval provider failure: report typed `error`, omit policy references, and continue deterministic evaluation; the audit records the retrieval status. A failure outside the adapter that prevents the workflow from running still follows the workflow fail-closed path. Workflow crash: persist escalated+routed, audit concise error code, never expose stack traces. MongoDB write failure: return retry/error, never claim approval; stable draft/request identity permits recovery after partial submission. Redis is a non-authoritative best-effort cache. Audit transitions include draft creation, submission, DMN evaluation, evidence attachment/omission, routing, human decisions and workflow failure; no private chain-of-thought.

Interrupted draft operations become recoverable on a later turn after five minutes: an existing pending request routes to review; an operation that created no request returns to collection. Attachment state is released for retry. MongoDB, audit writes and local filesystem operations are not a distributed transaction. Review and override updates compare the previously stored timestamp/status; delayed workflow writes cannot overwrite human outcomes.

## Implementation choices and limits

- Preserve existing calendar-day counting; no holiday/weekend calendar is invented.
- Retain DeepSeek candidate interpretation and existing OpenAI embedding provider; no provider migration.
- Engineering overlap demo uses two approved teammates on 2026-10-12 through 2026-10-14 only; requester is excluded.
- No distributed jobs or new infrastructure. Process-crash recovery and external provider/browser validation must be reported with actual test evidence.
- Environment configuration: `ORGANIZATION_TIMEZONE=Asia/Karachi`, `SICK_EVIDENCE_THRESHOLD_DAYS=3`. Calendar bounds are 366 days; reimbursement policy amounts are USD and no currency conversion is introduced.
- `python -m tests.migrate_legacy_evidence` (from backend) is a dry-run migration for historical invalid awaiting_evidence statuses/decisions. `--apply` explicitly routes those legacy requests to review. It is not run automatically against application data.
- Existing dormant extraction/evaluation modules remain outside the active graph. Neither chat nor traditional forms calls them.
- Chat preserves identity across turns in the mounted page. Navigation/reload starts a fresh UI conversation; draft restoration UI and a retention policy are deferred. The server still enforces ownership for every saved conversation ID.
