# SOP Forge conversation engine refactor report

Date: 2026-09-06. Branch: `codex/conversation-engine-refactor`. Inspected baseline: local main `2d47676`. No merge or deployment was performed. Implementation follows the supplied specification and inspected runtime code; older repository documentation was not used as implementation authority.

## A. Architecture Before

`/api/request/assistant` asked DeepSeek to choose ASK/SUBMIT/ESCALATE and reconstruct state from browser history. Its short-message greeting shortcut swallowed real answers. `_set_defaults` supplied invented dates, categories, amounts and access details. Submission then ran another LLM extraction inside LangGraph before DMN. Evidence logic returned awaiting_evidence values absent from request enums, trusted submitted evidence fields, and could approve a required-evidence request merely because a file existed. Evidence authorization referenced department attributes absent from the request/user model. Engineering overlap was returned for every date range. SHA-256 values were described and used as semantic vectors.

## B. Architecture After

The mounted chat sends message + conversation ID. MongoDB owns the draft. A single candidate interpreter proposes facts and conversational intent. Python merges corrections, checks field-family coherence, resolves dates, validates request-specific schemas and computes the next action. Complete drafts receive live HRMS/policy preflight, then the planner selects submission or review. Both actions enter the governed graph, which refreshes authoritative inputs, runs DMN, audits and persists valid lifecycle enums. Employee wording is selected from the persisted result.

Traditional forms use the same normalizer and governed graph. Neither chat nor forms calls the legacy extraction node. Evidence collection happens on drafts; required evidence, attached or omitted, requires human review. No new infrastructure or vector database was introduced.

See [the runtime architecture](../architecture/SOP_FORGE_PHASE1_RUNTIME_ARCHITECTURE.md) for the state machine and trust boundaries.

## C. Files Added

| File | Responsibility |
|---|---|
| `docs/architecture/SOP_FORGE_PHASE1_RUNTIME_ARCHITECTURE.md` | Code-derived design, created before implementation and updated to match the implementation. |
| `docs/reports/SOP_FORGE_CONVERSATION_ENGINE_REFACTOR_REPORT.md` | This implementation and verification record. |
| `backend/app/models/draft.py` | Owned draft schema, transient states, revision, preflight and last server question. |
| `backend/app/services/candidate_extraction.py` | One DeepSeek candidate extraction; clearly limited offline development interpreter. |
| `backend/app/services/normalization.py` | Date arithmetic, field families and shared request-schema boundary. |
| `backend/app/services/conversation_service.py` | Draft persistence/merge, preflight, deterministic planner, consent guards, submission and truthful status. |
| `backend/app/services/policy_retrieval.py` | Typed retrieval adapter (`match`, `no_match`, `degraded`, `error`) around the current MongoDB/Python implementation. |
| `backend/tests/fakes.py` | Isolated Mongo-compatible test adapter; never used for application persistence. |
| `backend/tests/test_conversation_engine.py` | 54 regression tests, including all 26 numbered specification scenarios and final hardening coverage. |
| `backend/tests/frontend_contract.test.js` | Executable JS API, file authorization and status-display contracts. |
| `backend/tests/redteam_conversations.py` | 30 engineer-authored live-provider conversation exercises and transcript capture. |
| `scripts/migrations/migrate_legacy_evidence.py` | Dry-run-by-default, idempotent repair for historical invalid evidence lifecycle values. |

## D. Files Modified

| File | Exact responsibility changed |
|---|---|
| `backend/app/api/request.py` | Replaced giant chat endpoint with service delegation; guarded workflow persistence against human decisions; sanitized failure text; recorded workflow failures; enforced direct-read ownership/department/organization scope. |
| `backend/app/api/evidence.py` | Added owned draft uploads; centralized authorization; bounded reads/signature checks; safe filenames; private metadata filtering; human-review-only request attachment updates and protected file serving. |
| `backend/app/config.py` | Organization timezone and positive configurable sick-evidence threshold. |
| `backend/app/models/audit.py` | Draft creation, attachment, omission and workflow failure audit events. |
| `backend/app/models/evidence.py` | Evidence can link to a draft before linking to a request. |
| `backend/app/schemas/request.py` | Request-specific categories/access/currency/numeric validation; normalized submissions; conversation ID, draft state, upload availability and retrieval mode; typed evidence metadata on request responses; removed suggestion options. |
| `backend/app/services/request_service.py` | Shared normalization; stable request identity; best-effort Redis; direct-read and review department checks; guarded human updates; more-info remains routed/escalated; overrides limited to approval/rejection. |
| `backend/app/services/sop_service.py` | Replaced hash similarity with explicitly degraded keywords; tagged real embedding provenance; excluded untagged legacy vectors; retained MongoDB/Python retrieval. |
| `backend/app/integrations/hrms_mock.py` | Restricted Engineering overlap to fixed October 12–14, 2026 scenario. |
| `backend/orchestration/graph.py` | Removed second interpretation; validated entry data; maintained enum-compatible failure outcomes. |
| `backend/orchestration/state.py` | Added authoritative evidence and typed retrieval-status fields; removed chain-of-thought terminology from active state documentation. |
| `backend/orchestration/edges.py` | Removed unsupported evidence-decision assumptions. |
| `backend/orchestration/nodes/intake.py` | Authoritative evidence lookup, requester exclusion from overlap, correct rolling 30-day arithmetic. |
| `backend/orchestration/nodes/dmn_rule_engine.py` | Normalized/coherent inputs; safe authoritative-data handling; removed retrieval availability from business decisions; corrected half-day/evidence rules and valid lifecycle results. |
| `backend/orchestration/nodes/escalate.py` | Removed invalid awaiting_evidence values; preserved deterministic resolved rejection. |
| `backend/orchestration/nodes/retrieve_policy.py` | Consumes the typed adapter, separates no-match from provider error, and supplies references without coupling either outcome to DMN. |
| `backend/orchestration/nodes/audit_log.py` | Added DMN event and retrieval-status recording; audit failure cannot silently complete approval. |
| `frontend/js/app.js` | Added shared HTML escaping and DOM-safe toast rendering. |
| `frontend/js/components/admin-panel.js`, `audit-viewer.js`, `dashboard.js`, `incidents.js` | Escaped API/user/policy/audit strings before template rendering. |
| `frontend/js/api.js` | Sends stable conversation ID instead of browser history. |
| `frontend/js/components/chat-assistant.js` | Server-directed draft upload control, no conversational suggestion cards/chips, safe message rendering, server-owned upload outcome wording. |
| `frontend/js/components/my-requests.js` | Correct final labels; escaped request content; rendered `size_bytes`; fetched evidence with bearer authentication into a blob viewer. |
| `frontend/js/components/review-panel.js` | Escaped employee/reasoning/policy/override content; authenticated evidence viewing; corrected size metadata. |
| `backend/pyproject.toml`, `backend/requirements.txt`, `requirements.txt` | Declared timezone data and directly used runtime dependencies where missing; existing version pins were not replaced. |

## E. RequestDraft

`request_drafts` holds authenticated employee ownership, fields, request type, date derivation basis, missing/ambiguous fields, evidence state/choice, last server question, preflight outcome, revision, timestamps and eventual request ID. Browser history is accepted for old-client compatibility but ignored by the business engine.

Turns compare-and-set the stored revision. Corrections replace only supplied facts. Changing duration removes derived end date; changing a range removes derived duration; changing a start date recalculates according to its recorded basis. Conflicting explicitly supplied values trigger clarification. Clear first-person illness can normalize a model-omitted sick category; relatives' illness cannot. A family-reason correction clears an inappropriate sick classification.

Submission claims the draft before creating a request, with a stable request ID. Repeat messages on a submitted draft return the persisted request. Interrupted operations recover on a later turn after five minutes; they never create a second request or assume approval. Finalized requests are not rewritten through chat.

## F. Conversation Planner

Python controls required-field questions, ambiguity, evidence preference, waiting for upload, submission and escalation for review. Policy-only turns do not merge hypothetical fields or submit. Complete drafts run preflight before the final action; the workflow independently refreshes HRMS/evidence/policy before deciding. Free-form policy text never supplies approval rules.

Unknown business facts stay missing. Short numerical answers use draft context. Bare yes/no, absence of a document and negative send instructions cannot become permission to submit without evidence, even if the interpreter proposes that choice. Ordinary employee preferences do not create misconduct incidents.

## G. Evidence Flow

- **Upload:** preference → awaiting_evidence draft → bounded, authorized file upload → evidence record linked to draft → normalized request → evidence record/metadata linked to request → routed/escalated for human evidence review.
- **Continue without:** explicit instruction → normalized request → routed/escalated, with “required supporting evidence was not provided” and an omission audit event.
- **Manager review:** same-department manager or authorized executive/admin can view authenticated file bytes and approve/reject. A file is never considered verified automatically. Final human decisions are protected from delayed workflow writes and later uploads.

Files remain local storage, as in the original application. No OCR, medical interpretation, malware scanning, or authenticity verification is claimed.

## H. DMN Changes

1. Request-specific normalization and field coherence precede branch selection.
2. Missing/invalid business data cannot acquire annual/read/amount defaults from extraction.
3. Python calculates inclusive calendar duration and rejects contradictory dates/counts.
4. Multi-day half-day requests cannot collapse to 0.5 days.
5. Organization-local date controls backdate evaluation; a resolved backdate rejection is preserved through graph routing.
6. HRMS failures/unknown employees route to review. Policy retrieval status and text are not DMN inputs.
7. Sick leave at the configured threshold requires human review whether evidence exists or not; missing evidence is not an automatic rejection.
8. Evidence existence comes from MongoDB, never submitted has_evidence/evidence IDs.
9. Engineering overlap is limited to two approved teammates on 2026-10-12 through 2026-10-14; intake excludes the requester.
10. Existing balance, blackout, expense limits and elevated-access review remain deterministic. Currency notation can normalize USD amounts; no foreign-exchange conversion is performed.

## I. Lifecycle Changes

No new `SOPRequest` enum values were necessary. Valid statuses remain in_progress, escalated, resolved, overridden; decisions remain pending, routed, approved, rejected. Submission starts in_progress/pending; deterministic approval/rejection ends resolved; exceptions end escalated/routed. More-info stays escalated/routed. Manager approval/rejection resolves; executive approval/rejection overrides.

Draft-only states are collecting, awaiting_evidence, attaching_evidence, submitting and submitted. The historical-invalid-state migration is explicit and dry-run by default. It was tested against isolated fixtures, **not applied to the configured database**.

## J. RAG

- Storage: existing MongoDB SOP documents and chunks.
- Embedding provider: existing OpenAI embedding endpoint/model setting.
- Real vectors: tagged by provider/model; Python cosine similarity only for compatible tagged vectors.
- Fallback: empty embedding marker plus normalized keyword retrieval, logged and returned as degraded_keyword for matching results.
- Legacy hash/untagged vectors: excluded from semantic scoring; re-ingestion is needed for trusted provider metadata.
- Adapter contract: typed `match`, `no_match`, `degraded`, and `error` outcomes.
- No matching policy: explicit no-policy answer; governed requests continue through the same deterministic DMN rules.
- Retrieval-provider error: explicit unavailable guidance and auditable status; it does not rewrite the business decision.
- Replacement boundary: a future vector store implements the adapter; workflow and DMN code do not change.
- **No dedicated vector database was added.** SHA-256 is not described as semantic retrieval.

## K. Security Boundaries

Browser messages and histories cannot establish roles, manager decisions, balances or file existence. Candidate facts are allowlisted and schema-validated; mixed field families cannot choose another DMN branch. Authenticated IDs own drafts. HRMS supplies balance/profile/overlap. MongoDB supplies evidence and human decisions. Direct request and evidence reads resolve employee ownership and department from server data, with missing relationships denied. Employee result text comes only from stored status/decision. Manager review, employee request detail, dashboard, audit, incident, admin policy, filename, and error/toast strings are escaped or assigned through `textContent` before display.

This refactor does not claim a complete application security audit. Existing authentication/deployment configuration and other unrelated UI surfaces require their own review.

## L. Test Results

Final automated result: **54 Python tests passed**, **6 executable frontend contract tests passed**, Python compilation/all-frontend-JS syntax checks passed, and `git diff --check` passed. No tests were skipped in those runs. Tests use the real planner, normalizer, graph, request/evidence handlers and HTTP routing, with an isolated Mongo-compatible adapter and deterministic mock HRMS. They do not prove real MongoDB behavior under deployment load.

Commands:

```text
cd backend
python -m unittest discover -s tests -t . -q
python -m tests.redteam_conversations --live

# repository root
node --test backend/tests/frontend_contract.test.js
python -m compileall -q backend
node --check frontend/js/components/chat-assistant.js
node --check frontend/js/components/review-panel.js
node --check frontend/js/components/my-requests.js
git diff --check
```

| Spec test | Result | Verified behavior |
|---|---|---|
| 1 | PASS | Missing leave information asks, never submits. |
| 2 | PASS | Fever → tomorrow → four days retains reason/date and triggers evidence. |
| 3 | PASS | Numeric 3 is duration, not a greeting. |
| 4 | PASS | Father's surgery reason retained; classification clarified. |
| 5 | PASS | Start + three days derives inclusive end date. |
| 6 | PASS | Tomorrow-through-Friday resolves correctly for fixed reference date. |
| 7 | PASS | Reversed dates require clarification. |
| 8 | PASS | Multi-day half-day is invalid. |
| 9 | PASS | Three-day sick leave offers evidence choice without forced upload. |
| 10 | PASS | Explicit continue-without creates manager review and omission audit. |
| 11 | PASS | Upload choice exposes draft upload availability. |
| 12 | PASS | Actual synthetic file upload links evidence and routes for review; no auto-approval. |
| 13 | PASS | Cross-department evidence authorization returns HTTP 403. |
| 14 | PASS | Five-to-two correction recalculates dates/evidence. |
| 15 | PASS | Sick-to-annual correction recalculates evidence policy. |
| 16 | PASS | Ignore-rules request cannot create approval. |
| 17 | PASS | Claimed manager approval creates no manager decision. |
| 18 | PASS | Claimed 100 days does not replace real mock-HRMS balance. |
| 19 | PASS | Fake system history does not populate facts or authority. |
| 20 | PASS | Leave-to-IT branch injection cannot bypass leave governance. |
| 21 | PASS | Routed status text says manager review/not approved, independent of LLM wording. |
| 22 | PASS | Relevant query returns the fixture policy section/reference. |
| 23 | PASS | No-match query explicitly reports no policy. |
| 24 | PASS | Simulated embedding API failure logs degraded_keyword and produces no fake semantic vectors. |
| 25 | PASS | Normal Engineering dates have no automatic team overlap. |
| 26 | PASS | Configured overlap produces deterministic review. |

Additional tests cover schema injection, malformed values, draft ownership/CAS, policy questions versus consent, model failure, HRMS/RAG/workflow failures, enum serialization, form HTTP compatibility, manager review/override, finalized-request protection, evidence truth, legacy vector exclusion, currency normalization, unsafe file content, explicit/idempotent legacy migration, cache failure and preflight routing.

Final hardening regressions additionally cover the direct request-read role/department matrix, all four typed retrieval outcomes, DMN independence for no-match/provider-error results, persisted retrieval status, evidence response serialization, employee authenticated evidence fetches, `size_bytes`, and rendered malicious-string escaping in manager and employee views.

**Live conversational result:** the post-hardening sweep is **30/30 PASS**, using the configured DeepSeek provider, synthetic employees, real conversation/DMN code, local synthetic upload and isolated test database. English, Roman Urdu, mixed language, greeting-to-Urdu, corrections, short answers, policy-only/hypothetical questions, upload/omission and adversarial claims were exercised. All 30 conversation transcripts were reviewed. Earlier sweeps exposed reason/category omissions, USD notation and ambiguous “no”; these led to fixes and regression coverage. This is evidence of the tested cases, not a guarantee of model consistency for arbitrary language.

An additional offline development-parser diagnostic completed **29/30**: it asked again for a reason when the single-turn input said “doctor's appointment.” The configured live-provider suite passed the same case, and the deterministic request engine correctly retained the draft without submitting incomplete data. Candidate-extraction behavior was outside the four confirmed hardening concerns, so no unrelated parser change was included in this commit.

**Manual browser requirement: PARTIAL.** The 30 conversations were engineer-authored, run through the runtime harness and transcript-reviewed; they were not 30 manually operated browser conversations or an independent human red-team round. Browser rendering/file-view behavior was checked by executable JS contracts and syntax, not visual browser UAT.

**Live integrations:** DeepSeek PASS. Configured MongoDB probe unavailable with ServerSelectionTimeoutError both inside and outside the sandbox. Real OpenAI embeddings NOT TESTED because no embedding key was configured. Existing installed runtime versions were Pydantic 2.13.4, FastAPI 0.133.1, LangGraph 1.2.11, langchain-openai 1.5.1 and Motor 3.7.1; a fresh dependency install against all manifests was not performed.

Generated test logs and conversation transcripts are intentionally excluded from version control. The durable regression runners and assertions remain in `backend/tests/`; results are summarized above.

## M. Final Hardening Review

| Concern | Finding | Root cause | Fix and files | Verification | Remaining limitation |
|---|---|---|---|---|---|
| Untrusted content in `innerHTML` | **Confirmed** | Review, request, dashboard, audit, incident, and admin templates interpolated API strings without a common output-encoding boundary. | Added `App.escapeHtml`, changed toast construction to DOM/text, and encoded affected dynamic strings in `frontend/js/app.js` and the review, request, dashboard, audit, incident, and admin components. | Node rendering regressions inject HTML event/script payloads; all six frontend contracts and all JS syntax checks pass. | This was a targeted source review of current first-party views, not a browser penetration test or CSP deployment review. |
| Direct `GET /api/request/{request_id}` authorization | **Confirmed** | The route restricted employees but treated every manager-or-higher role as organization-wide. | Added `can_access_request` in `backend/app/services/request_service.py` and enforced it in `backend/app/api/request.py`: own request for any role, same-department employee requests for managers, organization-wide for executives/admins. | HTTP regression covers employee own/cross, manager own/same/cross, executive, and admin responses. | Department membership still depends on authoritative and current `users.department_id` data. |
| RAG no-match coupled to DMN escalation | **Confirmed** | `retrieve_policy` mapped empty results to `policy_unavailable`; DMN treated that flag as an authoritative failure. | Added `backend/app/services/policy_retrieval.py`; graph retrieval now returns typed outcomes and DMN no longer reads retrieval state. Audit details record the outcome. | Tests cover `MATCH`, `NO_MATCH`, `DEGRADED`, `ERROR`; valid requests still follow deterministic approval rules under no-match and provider error. | A workflow-level failure outside the adapter still routes through the existing fail-closed workflow path. Real semantic embeddings remain untested. |
| Employee evidence response/viewer contract | **Confirmed** | `SOPRequest` stored evidence fields, but response schemas dropped them; My Requests used `size` and a direct protected URL without bearer authentication. | Added typed `EvidenceMetadata`, `has_evidence`, and `evidence_list` to request response/list schemas; employee viewer uses `size_bytes` and authenticated blob fetching. | Python serialization assertion plus Node authenticated-fetch/render tests pass; existing evidence authorization tests remain green. | Local file storage durability, malware scanning, OCR, and authenticity verification remain outside Phase 1. |

Dependency review: the DMN imports neither the retrieval adapter nor retrieval status. The workflow depends only on the adapter contract and generic chunks/status. Replacing MongoDB/Python scoring with another vector implementation requires an adapter implementation change, not DMN or workflow rule changes.

## N. Remaining Known Issues

1. Real MongoDB persistence, indexes/concurrency under multiple app workers, and deployment integration still need verification once the configured database is reachable. No application database was modified by the test harness.
2. Historical invalid awaiting_evidence request records require the supplied explicit migration before rollout. The current database could not be inspected or migrated.
3. Real semantic embedding success and the actual deployed policy corpus were not exercised. Keyword retrieval is intentionally limited; legacy chunks need re-ingestion to gain trusted embedding metadata.
4. Independent human/browser red-team testing is pending. The development interpreter is deliberately limited; its diagnostic passed 29/30 and missed “doctor's appointment” as a reason. Language-provider outages return retry rather than claiming equivalent offline understanding. Some evidence replies remain repetitive.
5. UI navigation/reload starts a fresh conversation; there is no draft restoration/retention interface. Saved IDs remain server-owned. Chat does not revise finalized requests.
6. Filesystem, MongoDB and audit writes are not one transaction. Crash recovery is triggered by a later conversation turn, not a background worker. Local upload storage must be persistent on the deployment host.
7. USD is the implemented reimbursement-policy currency; inclusive calendar days are used for leave. Arbitrary date phrases can require clarification. No holiday calendar, OCR, authenticity verification or new HR incident classifier was added.
8. Dependency manifests have pre-existing version differences. Tests used the installed environment, not a fresh production image. Production readiness is not claimed.

## O. Demo Readiness

READY WITH KNOWN LIMITATIONS

The implementation is ready for the next human red-team milestone with the integration/browser limitations above. Before rollout, restore database connectivity, inspect/migrate legacy states, validate the real policy corpus and run authenticated employee/manager browser flows. Main was not merged.
