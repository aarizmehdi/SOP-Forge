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

    from app.database import get_mongodb_client
    from app.services.policy_retrieval import PolicyRetrievalStatus, get_policy_retrieval_adapter

    client = get_mongodb_client()
    try:
        db = client.get_default_database()
    except Exception:
        db = client["sopforge"]

    result = await get_policy_retrieval_adapter().retrieve(
        db,
        query,
        top_k=5,
        category=request_type if request_type != "other" else None,
    )
    policy_refs = [item["ref"] for item in result.chunks]
    policy_text = "\n\n---\n\n".join(
        f"[{item['ref']}] (similarity: {item['similarity_score']:.2f})\n{item['chunk_text']}"
        for item in result.chunks
    )
    if result.status == PolicyRetrievalStatus.NO_MATCH:
        policy_text = "No matching SOP policy was found for this request."
        logger.info("Retrieve Policy: No relevant policy chunks found")
    elif result.status == PolicyRetrievalStatus.ERROR:
        policy_text = "Policy guidance is temporarily unavailable."
        logger.warning("Retrieve Policy: Provider returned an error outcome")
    else:
        logger.info("Retrieve Policy: Found %s relevant policy chunks (%s)", len(result.chunks), result.status.value)

    return {
        "retrieval_status": result.status.value,
        "retrieved_policy_refs": policy_refs,
        "retrieved_policy_text": policy_text,
    }
