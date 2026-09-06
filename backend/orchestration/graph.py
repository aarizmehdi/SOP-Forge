"""
SOP Forge — Main LangGraph workflow definition.
Assembles the full StateGraph as described in PRD Section 7:

    START → intake → retrieve_policy → evaluate → check_confidence
      ├─ (high confidence) → auto_decide → audit_log → END
      └─ (low confidence)  → escalate → override_check → audit_log → END
"""

import logging

from langgraph.graph import END, StateGraph

from orchestration.edges import check_confidence
from orchestration.nodes.audit_log import audit_log
from orchestration.nodes.auto_decide import auto_decide
from orchestration.nodes.escalate import escalate
from orchestration.nodes.dmn_rule_engine import dmn_rule_engine
from orchestration.nodes.intake import intake
from orchestration.nodes.override_check import override_check
from orchestration.nodes.retrieve_policy import retrieve_policy
from orchestration.state import RequestState

logger = logging.getLogger(__name__)


def build_sop_graph() -> StateGraph:
    """
    Build the SOP request evaluation LangGraph workflow.
    
    Graph structure (PRD Section 7):
        intake → retrieve_policy → dmn_rule_engine → check_confidence (conditional)
            ├─ auto_decide → audit_log → END
            └─ escalate → override_check → audit_log → END
    """
    workflow = StateGraph(RequestState)

    # ── Add Nodes ──
    workflow.add_node("intake", intake)
    workflow.add_node("retrieve_policy", retrieve_policy)
    workflow.add_node("dmn_rule_engine", dmn_rule_engine)
    workflow.add_node("auto_decide", auto_decide)
    workflow.add_node("escalate", escalate)
    workflow.add_node("override_check", override_check)
    workflow.add_node("audit_log", audit_log)

    # ── Add Edges ──
    # Both chat and forms are already normalized; there is no second interpretation.
    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "retrieve_policy")
    workflow.add_edge("retrieve_policy", "dmn_rule_engine")

    # Conditional edge: dmn_rule_engine → auto_decide OR escalate
    workflow.add_conditional_edges(
        "dmn_rule_engine",
        check_confidence,
        {
            "auto_decide": "auto_decide",
            "escalate": "escalate",
        },
    )

    # Auto-decide path → audit_log → END
    workflow.add_edge("auto_decide", "audit_log")

    # Escalate path → override_check → audit_log → END
    workflow.add_edge("escalate", "override_check")
    workflow.add_edge("override_check", "audit_log")

    # Terminal: audit_log → END
    workflow.add_edge("audit_log", END)

    return workflow


# ── Compile the graph ──
_compiled_graph = None


def get_compiled_graph():
    """Get or create the compiled LangGraph workflow."""
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_sop_graph()
        _compiled_graph = workflow.compile()
        logger.info("SOP evaluation graph compiled successfully")
    return _compiled_graph


async def run_request_workflow(
    request_id: str,
    employee_id: str,
    employee_code: str,
    request_type: str,
    submitted_data: dict,
) -> dict:
    """
    Run the full SOP request evaluation workflow.
    
    This is the main entry point called by the API when a request is submitted.
    Returns the final state after all nodes have executed.
    """
    from app.services.normalization import normalize_submission
    submitted_data = normalize_submission(request_type, submitted_data)
    graph = get_compiled_graph()

    initial_state: RequestState = {
        "request_id": request_id,
        "employee_id": employee_id,
        "employee_code": employee_code,
        "request_type": request_type,
        "submitted_data": submitted_data,
        "retrieved_policy_refs": [],
        "retrieved_policy_text": "",
        "extracted_variables": {},
        "dmn_result": False,
        "decision": "pending",
        "confidence": 1.0,
        "evaluation_reasoning": "",
        "status": "in_progress",
        "sla_deadline": None,
        "override_log": [],
        "live_data": {},
        "error": None,
    }

    logger.info(f"Running SOP workflow for request {request_id} ({request_type})")

    try:
        # Run the graph asynchronously
        final_state = await graph.ainvoke(initial_state)
        logger.info(
            f"Workflow completed for {request_id}: "
            f"decision={final_state.get('decision')}, "
            f"status={final_state.get('status')}, "
            f"confidence={final_state.get('confidence', 0):.2f}"
        )
        return final_state
    except Exception as e:
        logger.error(f"Workflow failed for {request_id}: {e}")
        return {
            **initial_state,
            "status": "escalated",
            "decision": "routed",
            "confidence": 0.0,
            "evaluation_reasoning": "Workflow failed. Request escalated for manual review.",
            "error": "workflow_failure",
        }
