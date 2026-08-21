"""
SOP Forge — Retrieve Policy node.
RAG retrieval against MongoDB SOP vector store.
"""

import logging

from orchestration.state import RequestState

logger = logging.getLogger(__name__)


async def retrieve_policy(state: RequestState) -> dict:
    """
    Retrieve relevant SOP policy chunks via cosine similarity search.
    """
    request_type = state["request_type"]
    submitted_data = state["submitted_data"]

    # Construct a contextual search query
    query_parts = [f"Policy for {request_type} request."]

    if request_type == "leave":
        leave_type = submitted_data.get("leave_type", "")
        reason = submitted_data.get("reason", "")
        query_parts.append(f"Leave type: {leave_type}.")
        query_parts.append(f"Reason: {reason}.")
        query_parts.append("Leave balance, notice period, blackout dates, approval criteria.")
    elif request_type == "reimbursement":
        category = submitted_data.get("category", "")
        query_parts.append(f"Reimbursement category: {category}.")
        query_parts.append("Expense limits, documentation requirements, approval authority.")
    elif request_type == "it_access":
        system = submitted_data.get("system_name", "")
        access = submitted_data.get("access_level", "")
        query_parts.append(f"System: {system}, Access level: {access}.")
        query_parts.append("Access control policy, security requirements, approval process.")

    query = " ".join(query_parts)
    logger.info(f"Retrieve Policy: Searching for: {query[:100]}...")

    # Perform vector search
    try:
        from app.services.sop_service import search_policy
        from app.database import get_mongodb_client

        client = get_mongodb_client()
        db = client.get_database()
        if not db.name:
            db = client["sopforge"]

        results = await search_policy(
            db,
            query=query,
            top_k=5,
            category=request_type if request_type != "other" else None,
        )

        if results:
            policy_refs = [r["ref"] for r in results]
            policy_text = "\n\n---\n\n".join(
                f"[{r['ref']}] (similarity: {r['similarity_score']:.2f})\n{r['chunk_text']}"
                for r in results
            )
            logger.info(f"Retrieve Policy: Found {len(results)} relevant policy chunks")
        else:
            policy_refs = ["No specific policy found"]
            policy_text = "No specific SOP policy found for this request type. Exercise caution and recommend escalation."
            logger.warning("Retrieve Policy: No policy chunks found")

    except Exception as e:
        logger.error(f"Retrieve Policy: Vector search failed: {e}")
        policy_refs = [f"Policy retrieval error: {e}"]
        policy_text = f"Error retrieving policy: {e}. Recommend manual escalation."

    return {
        "retrieved_policy_refs": policy_refs,
        "retrieved_policy_text": policy_text,
    }
