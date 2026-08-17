# SOP Forge - Master AI Agent Context (Brain File)

**Target Audience:** External AI systems, Agentic coders, and LLMs analyzing this repository.
**Project Name:** SOP Forge
**Description:** Internal Organizational SOP AI Agent — Governed Employee Request Engine. It converts physical/PDF SOP manuals into a queryable rule engine to evaluate employee requests (e.g., leave applications) against live data and policy limits.

---

## 1. High-Level Architecture
This system is an orchestration layer over existing HRMS/payroll systems. It is NOT a general-purpose chatbot. It enforces deterministic workflow control using LangGraph.

**Flow:**
`Employee Portal (Frontend SPA)` → `FastAPI Backend` → `LangGraph (AI Orchestration)`

*   **Knowledge Base:** RAG (Retrieval-Augmented Generation) against a PostgreSQL vector store (`pgvector`).
*   **Decision Engine:** DeepSeek V4 Pro (LLM) evaluates requests.
*   **DMN Engine:** A strict Python deterministic math bounds checker (Decision Model and Notation) that overrides LLM hallucinations.
*   **Audit Trail:** Immutable logging in PostgreSQL.
*   **State:** In-progress requests stored in Redis.

---

## 2. Recent Conversation & Development History (Context for Next AI)

We have heavily modified the AI Chat Assistant to be "Stanford-level" intelligent and highly defensive against edge cases:
1. **Dynamic LLM Responses:** Ripped out hardcoded robot responses. The AI generates contextual final responses (Approved/Escalated/Declined) based on actual system reasoning, and natively matches the user's language (e.g. if the user speaks Roman Urdu like "chutti chahiye", the AI replies in Roman Urdu).
2. **Live Data Injection:** The AI Chat Assistant's prompt now dynamically injects the user's live HRMS leave balances *during* the chat so it can proactively warn the user if they are exceeding limits before they even hit "submit".
3. **Hard Python Guardrails (Anti-Hallucination):** The AI prompt requires `reason` and `start_date` before submitting. If the LLM hallucinates and sends an action of `SUBMIT` with a blank reason or date, Python code in `request.py` forcefully intercepts it and converts the action to `ASK`. Zero hallucination tolerance.
4. **Dedicated HR Incidents Tab:** Users were trying to "trash talk" the AI (e.g. "I want to flirt"). Originally this just went to the Audit Log or Manager Review. The user requested a completely segregated section. 
   - *Status:* We implemented the backend `HRIncident` model and API (`/api/incidents`), and wired the `ESCALATE` action to write here instead of the audit trail. The frontend tab is partially built.

---

## 3. Current State & Next Steps

The very next step is to run a rigorous **Automated QA Simulation Suite**:
- We built `scripts/qa_simulator.py` which uses `httpx` to ping the `POST /api/request/assistant` endpoint.
- It tests:
  1. Trash Talk (Expected: routes to `HRIncident`).
  2. Missing Variables (Expected: Python hard override forces `ASK`).
  3. DMN Math Bounds (Expected: 50 days leave fails DMN check, overrides AI, routes to Manager).
  4. Roman Urdu Happy Path (Expected: Approved).
- **Issue:** The script currently hit a `ReadTimeout` because the `httpx` default 5-second timeout is too short for local LLM calls. 
- **Action Needed by Next Agent:** Run `python scripts/qa_simulator.py` (which now has a 30s timeout), verify the results, and fix any backend bugs discovered by the simulation. Then, finish the frontend `incidents.js` UI for HR managers to view the flagged chats.

---

## 4. Directory Structure (Context Map)

```text
SOP FORGE/
├── backend/                  # Python backend application
│   ├── app/                  # FastAPI main application logic
│   │   ├── api/              # API endpoints/routers (incident.py, request.py, auth.py)
│   │   ├── auth/             # JWT authentication and Role-Based Access Control
│   │   ├── models/           # SQLAlchemy database models (tables)
│   │   ├── schemas/          # Pydantic models (validation/serialization)
│   │   ├── services/         # Core business logic (DB CRUD, etc.)
│   │   └── integrations/     # API bridge layer (mocked HRMS/Payroll connectors)
│   ├── orchestration/        # AI logic and LangGraph state machines
│   │   ├── nodes/            # Python files for each node (dmn_rule_engine.py, evaluate.py)
│   │   └── graph.py          # The core routing logic
├── frontend/                 # Vanilla JS Single Page Application
│   ├── js/                   # Frontend logic
│   │   ├── api.js            # Frontend API client
│   │   ├── router.js         # Hash-based SPA routing
│   │   └── components/       # Reusable JS UI components (chat-assistant.js, incidents.js)
│   ├── index.html            # Main entry point (Sidebar navigation)
│   └── index.css             # Main stylesheet
├── scripts/                  # Helper scripts (qa_simulator.py)
├── docker-compose.yml        # Infrastructure definitions (PostgreSQL + pgvector, Redis)
└── sopforge.md               # **THIS FILE** (Master Context File)
```

## 5. Key Design Principles (For AI Developers)
*   **No Silent Guesses:** The LLM is never allowed to guess if policy is missing. Low confidence strictly triggers escalation.
*   **DMN Overrides:** Never trust the AI to do math or bounds checking. The `dmn_rule_engine` acts as the final deterministic arbiter before Auto-Decision.
*   **Separation of Concerns:** The `backend/app` layer handles HTTP and CRUD. The `backend/orchestration` layer handles LLM interactions and state machine flow. 
*   **Roman Urdu Support:** The system officially supports processing intent in Roman Urdu/Hindi.
*   **Zero-Hallucination Guardrails:** Python interceptions at the API layer protect downstream systems from incomplete LLM JSON objects.
