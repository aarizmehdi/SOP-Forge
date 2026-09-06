# SOP Forge Conversational AI V2

## Purpose

Conversational AI V2 replaces the form-like chat wizard with a bounded, professional assistant while preserving the existing authority boundaries. The language model interprets and explains. The server owns identity, conversation scope, validated facts, evidence state, lifecycle transitions, and completeness. The DMN workflow remains the only approval, rejection, and routing authority. Policy retrieval remains behind the existing adapter and supplies explanatory context only.

This document is the implementation specification for V2. The current source code is the baseline; older design and report documents are not runtime authority.

## Authority boundaries

### LLM conversation layer

The conversation layer has two responsibilities.

**Turn understanding** receives the latest employee message plus bounded server-owned context. It returns a validated structure containing:

- conversational intent;
- explicit facts and explicit corrections;
- policy, balance, help, explanation, and in-domain general-question signals;
- a proposed request type within the selected domain;
- an inferred leave category, its confidence, and whether each material value was explicit or inferred;
- language and confidence signals;
- a typed governance or security concern and confidence.

It cannot assert identity, approval, rejection, routing, balances, permissions, evidence existence, manager approval, or executable policy results. Model values outside server-approved fields and taxonomies are discarded. A configurable confidence threshold controls whether an inferred material category is accepted.

**Response composition** receives a bounded, authoritative server response plan after validation, retrieval, and any DMN execution. It writes professional employee-facing wording for the selected domain and established language. It cannot alter the response type, UI state, allowed actions, validated fields, request identifier, status, decision, or review destination. Deterministic wording is used only when the provider is unavailable or returns invalid output.

### Server and Python

The server owns:

- authenticated employee identity and draft ownership;
- the immutable selected domain;
- the authoritative `RequestDraft` fields and validated dates;
- bounded recent conversational turns;
- field completeness and ambiguity;
- stable language selection;
- evidence existence confirmed from persistence;
- evidence-gate and terminal transitions;
- authorization, concurrency control, and request identifiers;
- typed incidents recorded independently from normal requests.

The browser sends only the current message and the employee-owned `conversation_id` after a domain has been selected. Browser transcripts are not accepted as business authority.

### DMN workflow

The existing request workflow and DMN rules remain authoritative for approval, rejection, and routing. Complete chat drafts and form submissions converge through the same validated request schemas and governed workflow. Missing or ambiguous facts never cause submission merely because the conversation layer is uncertain. The DMN backdate rule remains a second safety layer after the earlier conversational validation.

### Policy retrieval

Policy questions use the existing `PolicyRetrievalAdapter` and preserve its `MATCH`, `NO_MATCH`, `DEGRADED`, and `ERROR` outcomes. Retrieved text may inform explanations and bounded category inference, but cannot approve a request or replace DMN decisions. A future vector-store replacement must require no change to conversation state or DMN semantics. V2 does not add Pinecone or multi-tenancy.

## Domain and lifecycle model

The client begins in `DOMAIN_SELECTION`, shows exactly these choices, and does not show an active composer:

- Leave & HR
- Expenses & Finance
- IT & System Access
- Policies & General

Selecting a domain calls an authenticated start endpoint. The server creates a new owned conversation, persists the immutable domain, and returns its `conversation_id` in `ACTIVE_CHAT`. Leave, expense, and IT domains can create only their corresponding request type. The policies domain answers organizational questions and never creates a request. A request for another domain produces guidance to start a new conversation; it never mutates the current scope.

The authoritative UI states are:

| State | Available controls | Server behavior |
| --- | --- | --- |
| `DOMAIN_SELECTION` | Four domain choices | No draft business flow exists yet. |
| `ACTIVE_CHAT` | Transcript, text composer, microphone, send | Interpret the latest turn, preserve the bounded transcript, validate facts, answer side questions, and collect a complete draft. |
| `EVIDENCE_GATE` | Transcript, `Upload Evidence`, `Skip Evidence` | Reject ordinary chat; accept only the authenticated upload or skip transaction. |
| `TERMINAL` | Transcript, authoritative result, `View Request`, `Start New Conversation` | Reject further chat with a typed closed-conversation error. |

One conversation represents one task. Approval, rejection, routing, submission with evidence, and submission without evidence close it. The response includes typed UI state, allowed actions, and structured terminal data containing request ID, status, decision, and review destination when known. The frontend renders the status title from that authoritative data. A model-written body may explain the result but cannot change it.

Starting over clears the client session and returns to `DOMAIN_SELECTION`; choosing a domain then creates a fresh server draft and identifier.

## Request collection

The server supplies the model with the selected domain, allowed field names and enum values, organization date, a compact draft summary, the last unresolved need, relevant policy excerpts when needed, and a bounded recent history. Structured draft fields remain the business memory. Recent turns provide conversational reference and prevent blind repetition.

Explicit facts and corrections are applied only after field-family, taxonomy, and type validation. Obvious leave categories may be inferred within `annual`, `sick`, `casual`, and `unpaid`. The server accepts an inferred category only at or above `CATEGORY_INFERENCE_CONFIDENCE_THRESHOLD`; otherwise it asks a contextual clarification. Organization policy context guides classifications such as a family surgery without adding organization-specific Python synonym trees.

Policy, balance, help, and explanation questions interrupt collection without changing or submitting the draft. The assistant answers the question, preserves all collected fields, and then offers contextual guidance toward the unresolved information. Confusion and frustration produce a new helpful explanation instead of repeating an identical prompt. Profanity alone does not change the session language or create an incident.

Language is selected from meaningful content and retained unless the employee explicitly asks to switch or sustained high-confidence evidence supports a switch. English, Roman Urdu, and reasonable code-switching are supported.

## Date handling

The conversation layer may propose a normalized date using the authoritative organization date. Python validates every proposed date before persistence. The deterministic parser also accepts common natural English and Roman Urdu expressions, including named months, ordinal dates, relative dates, and `this` or `next` weekdays. Ambiguous numeric dates such as `10/11` remain unresolved and receive a natural clarification describing the alternatives.

Employees never see parser identifiers, planner actions, internal field names, raw exceptions, or instructions to enter ISO dates. A deterministic pre-submit check rejects past start dates conversationally and keeps the draft active. The existing DMN zero-backdate rule remains authoritative during final evaluation.

## Evidence transaction gate

When the configured evidence threshold applies, the server enters `EVIDENCE_GATE` and gives one clear explanation. The ordinary composer, microphone, and send controls are unavailable. The UI exposes exactly two primary transactional actions:

- `Upload Evidence`, which opens the file picker and posts to the authenticated draft upload endpoint;
- `Skip Evidence`, which calls a dedicated authenticated endpoint.

The server does not infer either action from chat text. Upload success is followed by a database check for the persisted attachment, then governed submission and closure. File presence is never treated as verification; requests requiring human evidence review are routed accordingly. Upload failure leaves the draft at `EVIDENCE_GATE` for retry or skip. Skip persists the explicit choice, executes the governed no-evidence route, records the omission, and closes the conversation. The configured evidence threshold is unchanged.

## Incidents

Conversation incidents are typed and separate from SOP requests. Allowed categories cover policy bypass attempts, authority impersonation, fraudulent authoritative claims, security or control manipulation, and serious threats or harassment. An incident is created only when the structured signal is meaningful and meets its configured confidence threshold. The suspicious claims are ignored for business authority while legitimate in-domain facts continue through the normal request flow. Swearing, criticism, frustration, short messages, and informal speech alone do not create incidents.

## Failure behavior

Invalid or unavailable turn-understanding output preserves the authoritative draft and uses a professional fallback that asks the employee to restate the relevant information. Invalid or unavailable response-composition output uses a deterministic fallback generated from safe response descriptors. Retrieval failures remain explanatory failures and do not change DMN behavior. Authoritative infrastructure failures retain the existing fail-closed human-review behavior. Interrupted attachment and submission transitions retain their recoverable compare-and-set protections.

## Acceptance criteria

V2 is accepted when all of the following are verified:

1. Domain selection creates an owned conversation; the policies domain cannot create a request and an active domain cannot be silently changed.
2. The assistant accepts obvious high-confidence category inference, including family-surgery context when policy supports it, and avoids a repeated generic category loop.
3. A side policy, balance, help, or explanation question preserves draft facts, answers the question, and resumes useful collection.
4. Server-owned bounded history supports references and varied guidance while browser-supplied history is absent from the authoritative contract.
5. Natural English and Roman Urdu dates resolve correctly; ambiguous numeric dates receive natural clarification; past dates are stopped before submission without exposing internal tokens or ISO instructions.
6. Meaningful language signals remain stable across isolated slang or profanity.
7. Governance manipulation can create a typed incident while the legitimate request continues; ordinary frustration does not create one.
8. Evidence-required drafts expose only upload and skip actions. Failed uploads remain gated. Successful upload and explicit skip each produce one governed request and close the conversation.
9. Closed conversations reject later text with a typed closed response or error and never replay an earlier approval or routing message.
10. Terminal responses expose authoritative status, decision, request ID, destination, UI state, and allowed actions; the frontend renders a deterministic status title.
11. The standard `/api/request/submit` form path still validates and executes through the existing request schemas and DMN workflow.
12. Existing ownership, authorization, attachment security, lifecycle serialization, failure recovery, audit, retrieval-status, and concurrency regressions continue to pass.
13. Permanent backend and frontend tests cover cases A through P in this specification, and the ignored live suite covers at least 30 adversarial, natural, English, Roman Urdu, code-switched, correction, side-question, frustration, evidence, policy, and terminal conversations when DeepSeek is configured.

## Implementation and verification

Implemented on `refactor/conversational-ai-v2`:

- Added authenticated domain-session creation, immutable domain scope, bounded server-owned recent turns, stable language tracking, compare-and-set persistence, evidence-gate enforcement, and typed closed-conversation errors.
- Split conversational work into structured turn understanding and bounded response composition. Added normalization for valid DeepSeek JSON variations and a conservative provider-failure repair path. The server continues to validate all facts and owns every lifecycle action.
- Added configurable confidence thresholds for inferred leave categories and typed incidents. Category inference receives the allowed taxonomy and retrieved active-policy context. Governance incidents are persisted separately while legitimate request facts remain governed by the selected domain.
- Added natural named-month, ordinal, relative, and qualified-weekday date parsing, ambiguous numeric-date clarification, and deterministic pre-submit backdate rejection. The DMN backdate rule remains unchanged.
- Added explicit start and evidence-skip APIs, database-confirmed evidence upload finalization, structured terminal results, and authoritative UI states/actions.
- Rebuilt the chat UI around `DOMAIN_SELECTION`, `ACTIVE_CHAT`, `EVIDENCE_GATE`, and `TERMINAL`, including the four domain choices, the exact upload/skip transaction gate, deterministic outcome titles, and new-conversation reset.
- Preserved the form submission endpoint, request schemas, workflow/DMN authority, retrieval adapter statuses, ownership checks, evidence authorization, and fail-closed workflow recovery.

Verification completed on 7 September 2026:

- Python: 73/73 tests passed with `python -m unittest tests.test_conversation_engine -q`.
- Frontend: 10/10 tests passed with `node --test backend/tests/frontend_contract.test.js`.
- Local bounded-fallback red team: 30/30 conversations passed.
- Live DeepSeek red team: 30/30 conversations passed using the configured provider.
- Python module compilation and JavaScript syntax checks passed.
- Generated red-team JSON and test logs remained under ignored `test-results/` and are not repository changes.

The automated red-team harness uses the isolated Mongo adapter and degraded keyword retrieval because semantic embeddings are unavailable in the test environment. It exercises the real conversation service, schemas, workflow, evidence handlers, and configured DeepSeek provider, but it is not browser UAT or human organizational policy review.
