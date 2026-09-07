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
- facts recovered from conversational references to prior server-owned employee turns;
- policy, balance, help, explanation, and in-domain general-question signals;
- a proposed request type within the selected domain;
- an inferred leave category, its confidence, and whether each material value was explicit or inferred;
- input-language signals used only to improve understanding;
- a typed governance or security concern and confidence.

It cannot assert identity, approval, rejection, routing, balances, permissions, evidence existence, manager approval, or executable policy results. Model values outside server-approved fields and taxonomies are discarded. A configurable confidence threshold controls whether an inferred material category is accepted.

**Response composition** receives a typed, authoritative server response plan after validation, retrieval, and any DMN execution. The plan includes the immutable output language, domain persona, latest employee message, known facts, unresolved concept, why the concept is needed, clarification attempt, prior question, and any side-question answer. The model chooses natural professional wording within that plan. `EVIDENCE_GATE` contains the category, working-day duration, evidence requirement, and the two available actions. Request `TERMINAL` contains the result, destination, and terminal actions. `incomplete_conversation` contains the unresolved concept and only the new-conversation action. Purpose-specific validators reject prose that uses the wrong output language, asks the wrong question, re-asks known information, repeats a prior clarification verbatim, contradicts state, omits evidence actions, exposes a UUID, invites more terminal chat, or promises unsupported follow-up. Invalid output is discarded and replaced with deterministic provider-failure wording.

### Server and Python

The server owns:

- authenticated employee identity and draft ownership;
- the immutable selected domain;
- the authoritative `RequestDraft` fields and validated dates;
- bounded recent conversational turns;
- field completeness and ambiguity;
- the employee's immutable selected output language;
- evidence existence confirmed from persistence;
- evidence-gate and terminal transitions;
- authorization, concurrency control, and request identifiers;
- typed incidents recorded independently from normal requests.

The browser sends the selected domain and language once to create a conversation. Afterward it sends only the current message and employee-owned `conversation_id`. Browser transcripts and later language signals are not accepted as business authority.

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

Selecting a domain advances to `LANGUAGE_SELECTION`; it does not create a server conversation. The employee must then choose exactly one output language:

- English (`en`)
- Roman Urdu in Latin script (`roman_urdu`)

Only the second selection calls the authenticated start endpoint. The server creates a new owned conversation and persists both the immutable domain and immutable output language. English conversations always produce English assistant replies, even when the employee writes in Roman Urdu, mixed language, slang, or another language. Roman Urdu conversations always produce Roman Urdu replies, even when the employee writes in English. The assistant never emits duplicate English and Roman Urdu versions. Input-language detection can help interpretation but cannot mutate the selected output language.

Leave, expense, and IT domains can create only their corresponding request type. The policies domain answers organizational questions and never creates a request. A request for another domain produces guidance to start a new conversation; it never mutates the current scope.

The authoritative UI states are:

| State | Available controls | Server behavior |
| --- | --- | --- |
| `DOMAIN_SELECTION` | Four domain choices | No draft business flow exists yet. |
| `LANGUAGE_SELECTION` | English and Roman Urdu choices | No server conversation exists yet. |
| `ACTIVE_CHAT` | Transcript, text composer, microphone, send | Interpret the latest turn, preserve the bounded transcript, validate facts, answer side questions, and collect a complete draft. |
| `EVIDENCE_GATE` | Transcript, `Upload Evidence`, `Skip Evidence` | Reject ordinary chat; accept only the authenticated upload or skip transaction. |
| `TERMINAL` | Request result: `View Request` and `Start New Conversation`; incomplete conversation: `Start New Conversation` only | Reject further chat with a typed closed-conversation error. |

One conversation represents one task. Approval, rejection, routing, submission with evidence, submission without evidence, and exhaustion of three clarification attempts close it. A request terminal response contains request ID, status, decision, and review destination. An `incomplete_conversation` terminal response contains no request identity or decision because no SOP request is created. The frontend renders the title and actions from that authoritative data. A model-written body may explain the result but cannot change it.

Starting over clears the client session and returns to `DOMAIN_SELECTION`; choosing a department and language then creates a fresh server draft and identifier.

## Request collection

The server supplies the model with the selected domain, locked output language, authenticated-employee context, allowed actions, lifecycle state, allowed field names and enum values, organization date, complete known and missing draft facts, the last requested concept, clarification counts, active policy excerpts, and bounded server-owned recent turns. Structured draft fields remain the business memory. Recent turns provide conversational reference and prevent blind repetition.

Turn understanding is semantic and holistic. Every employee message is evaluated for all useful facts, even when it also answers a side question or supplies information beyond the current requested concept. One sentence can therefore supply a request category, dates, duration, reason, amount, system, access level, and justification as applicable. The employee does not need to use backend field names or enum labels. Misspellings, indirect phrasing, English, Roman Urdu, mixed-language input, and slang are interpretation concerns for the model, while server schemas remain the acceptance boundary.

Explicit facts and corrections are applied only after field-family, taxonomy, and type validation. Provider output and the bounded deterministic parser are repaired field by field: non-conflicting explicit parser facts supplement omitted model fields, while an explicit model correction wins for the corrected field. A partial model result therefore cannot erase an explicit duration, date, amount, system name, or other independently bounded fact.

Obvious leave categories may be inferred within `annual`, `sick`, `casual`, and `unpaid`. The server accepts an inferred category only at or above `CATEGORY_INFERENCE_CONFIDENCE_THRESHOLD`; otherwise it asks a contextual clarification. The active policy defines the employee's own illness, injury, medical recovery, and appointments as sick leave, so a clear illness, doctor's rest instruction, broken leg, or fractured ankle is a strong sick-leave candidate. A relative's medical event remains a casual-leave candidate under the active policy. The turn-understanding contract preserves the employee's free-form explanation, and a generic server safety rule retains a substantive answer when `reason`, expense `description`, or access `justification` is the last requested required field.

Conversational references are resolved against bounded server-owned employee turns. The model returns separately typed `recovered_facts` and a reference flag; a bounded server fallback can recover the last requested concept from prior turns when the provider is unavailable. Reference phrases such as “I already told you” and “same reason” are never persisted as the reason, description, or justification. Corrections still take precedence over recovered and earlier facts.

Policy, balance, help, and explanation questions interrupt collection without changing or submitting the draft. The assistant answers first, preserves all collected fields, and resumes the unresolved concept with context-aware wording. Confusion and frustration produce a respectful explanation of what is already known and what is still needed. Profanity alone does not change the session language or create an incident.

### Clarification and anti-loop behavior

The server tracks clarification attempts by business concept. After every employee reply, turn understanding, recovered context, accepted inference, corrections, and draft validation run before any follow-up question is chosen. A semantically sufficient answer advances immediately.

For a genuinely unresolved concept, attempt one asks naturally. Attempt two explains more clearly what is needed and why, with an example when useful. Attempt three gives a final concise clarification. The composer receives the prior question and may not repeat it verbatim. If the next employee turn still does not supply usable information, the server closes the draft as `incomplete_conversation`, creates no SOP request, and exposes only `Start New Conversation`. Further messages on that conversation ID are rejected by the existing closed-conversation boundary.

### Professional personas

Response composition uses a domain-specific professional role: an HR and leave specialist, finance operations specialist, IT access specialist, or organizational policy specialist. Replies must remain respectful, calm, courteous, patient, clear, helpful, and context-aware. They must not mirror profanity, become argumentative, or expose parser and planner mechanics. The model controls normal phrasing; deterministic sentences are reserved for provider failure or invalid model output.

## Date handling

The conversation layer may propose a normalized date using the authoritative organization date. Python validates every proposed date before persistence. The deterministic parser also accepts common natural English and Roman Urdu expressions, including named months, ordinal dates, relative dates, and `this` or `next` weekdays. It corrects a close, isolated spelling error in common English date words, so `tommorow till 20 septemeber` resolves safely. Ambiguous numeric dates such as `10/11` remain unresolved and receive a natural clarification describing the alternatives.

The seeded active SOP defines leave entitlements, sick-evidence thresholds, and instance limits in working days. Leave normalization, derived end dates, extracted duration metadata, evidence checks, HRMS balance comparison, and DMN evaluation therefore use inclusive Monday-through-Friday working-day arithmetic. For example, three working days starting Friday end on Tuesday. The current source does not provide an authoritative organization holiday calendar, so public holidays are not subtracted; adding that calendar requires an authoritative HRMS or policy source rather than an invented list.

Employees never see parser identifiers, planner actions, internal field names, raw exceptions, or instructions to enter ISO dates. A deterministic pre-submit check rejects past start dates conversationally and keeps the draft active. The existing DMN zero-backdate rule remains authoritative during final evaluation.

## Evidence transaction gate

When the configured evidence threshold applies, the server enters `EVIDENCE_GATE` and gives one clear explanation. The ordinary composer, microphone, and send controls are unavailable. The UI exposes exactly two primary transactional actions:

- `Upload Evidence`, which opens the file picker and posts to the authenticated draft upload endpoint;
- `Skip Evidence`, which calls a dedicated authenticated endpoint.

The server does not infer either action from chat text. Upload success is followed by a database check for the persisted attachment, then governed submission and closure. File presence is never treated as verification; requests requiring human evidence review are routed accordingly. Upload failure leaves the draft at `EVIDENCE_GATE` for retry or skip. Skip persists the explicit choice, executes the governed no-evidence route, records the omission, and closes the conversation. The configured evidence threshold is unchanged.

## Incidents

Conversation incidents are typed and separate from SOP requests. Allowed categories cover policy bypass attempts, authority impersonation, fraudulent authoritative claims, security or control manipulation, and serious threats or harassment. An incident is created only when the structured signal is meaningful and meets its configured confidence threshold. The suspicious claims are ignored for business authority while legitimate in-domain facts continue through the normal request flow. Swearing, criticism, frustration, short messages, and informal speech alone do not create incidents.

## Failure behavior

Invalid or unavailable turn-understanding output preserves the authoritative draft and uses bounded extraction for clear facts. A valid but partial model candidate is repaired without replacing unrelated model values. Invalid or semantically inconsistent response-composition output uses a deterministic fallback generated from the typed response plan. Retrieval failures remain explanatory failures and do not change DMN behavior. Authoritative infrastructure failures retain the existing fail-closed human-review behavior. Interrupted attachment and submission transitions retain their recoverable compare-and-set protections.

## Acceptance criteria

V2 is accepted when all of the following are verified:

1. Domain selection creates an owned conversation; the policies domain cannot create a request and an active domain cannot be silently changed.
2. The assistant accepts obvious high-confidence category inference, including family-surgery context when policy supports it, and avoids a repeated generic category loop.
3. A side policy, balance, help, or explanation question preserves draft facts, answers the question, and resumes useful collection.
4. Server-owned bounded history supports references and varied guidance while browser-supplied history is absent from the authoritative contract.
5. Natural English and Roman Urdu dates resolve correctly; ambiguous numeric dates receive natural clarification; past dates are stopped before submission without exposing internal tokens or ISO instructions.
6. Domain selection is followed by required language selection; no conversation starts before both are selected, and every reply obeys the immutable English or Roman Urdu output choice regardless of input language.
7. Governance manipulation can create a typed incident while the legitimate request continues; ordinary frustration does not create one.
8. Evidence-required drafts expose only upload and skip actions. Failed uploads remain gated. Successful upload and explicit skip each produce one governed request and close the conversation.
9. Closed conversations reject later text with a typed closed response or error and never replay an earlier approval or routing message.
10. Request terminal responses expose authoritative status, decision, request ID, destination, UI state, and allowed actions; incomplete terminal responses expose no request result and only allow a new conversation.
11. The standard `/api/request/submit` form path still validates and executes through the existing request schemas and DMN workflow.
12. Existing ownership, authorization, attachment security, lifecycle serialization, failure recovery, audit, retrieval-status, and concurrency regressions continue to pass.
13. Permanent backend and frontend tests cover cases A through P in this specification, and the ignored live suite covers at least 30 adversarial, natural, English, Roman Urdu, code-switched, correction, side-question, frustration, evidence, policy, and terminal conversations when DeepSeek is configured.
14. A clear self-injury is retained as the reason and confidently classified as sick leave under the active policy; a direct `5 days` answer is stored immediately and the next response cannot ask for duration again.
15. Red-team PASS requires both correct authoritative state and semantically correct employee-facing text, including concept-specific questions, evidence explanation, terminal closure, and absence of unsupported promises.
16. Every turn can contribute multiple valid facts, and high-confidence policy-supported inference advances without asking employees for backend taxonomy words.
17. References and corrections recover employee-supplied context without persisting the reference phrase as a business fact.
18. A concept receives at most three progressively clearer clarification prompts; the next unresolved response closes with `incomplete_conversation` and creates no SOP request.

## Current implementation

Implemented on `fix/intelligent-conversation-experience`:

- Added the department-to-language start flow, immutable server-owned output language, bounded server-owned recent turns, compare-and-set persistence, evidence-gate enforcement, and typed closed-conversation errors.
- Split conversational work into structured turn understanding and bounded response composition. Added normalization for valid DeepSeek JSON variations and a conservative provider-failure repair path. The server continues to validate all facts and owns every lifecycle action.
- Added configurable confidence thresholds for inferred leave categories and typed incidents. Category inference receives the allowed taxonomy and retrieved active-policy context. Governance incidents are persisted separately while legitimate request facts remain governed by the selected domain.
- Added natural named-month, ordinal, relative, and qualified-weekday date parsing, ambiguous numeric-date clarification, and deterministic pre-submit backdate rejection. The DMN backdate rule remains unchanged.
- Added explicit start and evidence-skip APIs, database-confirmed evidence upload finalization, structured terminal results, and authoritative UI states/actions.
- Rebuilt the chat UI around `DOMAIN_SELECTION`, `LANGUAGE_SELECTION`, `ACTIVE_CHAT`, `EVIDENCE_GATE`, and `TERMINAL`, including the four domain choices, two explicit language choices, the exact upload/skip transaction gate, deterministic outcome titles, and new-conversation reset.
- Preserved the form submission endpoint, request schemas, workflow/DMN authority, retrieval adapter statuses, ownership checks, evidence authorization, and fail-closed workflow recovery.
- Repaired partial candidates field by field, strengthened the free-form reason contract and last-required-explanation safety rule, and added policy-guided self-injury inference.
- Added typo-tolerant date-word normalization and aligned leave range, derived end date, evidence threshold, extracted metadata, HRMS balance, and DMN calculations with the seeded SOP's working-day semantics.
- Expanded structured turn understanding to handle holistic facts, separately typed recovered facts, conversational references, policy context, and immutable language context.
- Replaced generic response descriptors with typed purpose plans and language-aware semantic output validation. Evidence messages cannot collect request facts, terminal messages cannot invite chat or make unsupported promises, and generated text that violates the plan is discarded.
- Added concept-specific clarification counters, varied second and third explanations, and a request-free `incomplete_conversation` closure after three unsuccessful clarification attempts.
- Extended permanent backend and frontend regressions for required language selection, immutable output language, holistic extraction, reference recovery, and incomplete terminal behavior.

The bounded deterministic parser remains a degraded provider-failure path and cannot match the model's open-ended semantic understanding. Public holidays are still excluded only when an authoritative organization calendar is added. Human browser testing and organizational policy review remain outside this architecture contract.
