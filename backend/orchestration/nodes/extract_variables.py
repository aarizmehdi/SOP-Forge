"""
SOP Forge — Extract Variables node.
LLM-based variable extraction. Decoupled from final decision making.
Outputs structured JSON (e.g. intent, requested_days, leave_type) based on Roman Urdu / English prompt.
"""

import json
import logging
import re

from app.config import get_settings
from orchestration.state import RequestState

logger = logging.getLogger(__name__)
settings = get_settings()


EXTRACTION_PROMPT = """You are an SOP (Standard Operating Procedure) extraction assistant for Aziz Jan Group.
Your task is to extract structured variables from an employee request and translate it if it is in Roman Urdu.
Do NOT evaluate whether the request should be approved or rejected. Simply extract the facts.

## Request Details
- **Type:** {request_type}
- **Employee:** {employee_code}
- **Submitted Data:** {submitted_data}

## Your Task
Extract the core variables from this request.
If the submitted data contains Roman Urdu text, translate its intent into English before extracting.
You MUST respond with ONLY a JSON object (no markdown, no extra text) containing these fields based on the type of request:

For Leave/Biometric/Overtime/General:
{{
    "intent": "<e.g., leave, overtime, missed_punch, general_inquiry>",
    "category": "<e.g., annual, sick, casual, etc. (if applicable)>",
    "days_requested": <number (if applicable)>,
    "hours_requested": <number (if applicable)>,
    "reason": "<translated English reason>",
    "confidence": <float between 0.0 and 1.0 representing how confident you are in your extraction>
}}

## Confidence Guidelines
- 0.90-1.00: Clear request, variables easily identified
- 0.50-0.89: Ambiguous request but mostly clear
- 0.00-0.49: Completely unclear or unparseable request
"""


async def extract_variables(state: RequestState) -> dict:
    """
    Extract variables using the LLM against the request.
    Falls back to a rule-based mock if no LLM is configured.
    """
    request_type = state["request_type"]
    employee_code = state.get("employee_code", "unknown")
    submitted_data = state["submitted_data"]

    logger.info(f"Extract Variables: Running AI extraction for {request_type} request")

    if settings.is_llm_configured:
        try:
            return await _extract_with_llm(request_type, employee_code, submitted_data)
        except Exception as e:
            logger.error(f"Extract Variables: LLM extraction failed, falling back to rules: {e}")

    # Fallback: rule-based extraction for development
    return await _extract_with_rules(request_type, submitted_data)


async def _extract_with_llm(request_type: str, employee_code: str, submitted_data: dict) -> dict:
    """Extract using DeepSeek via LangChain OpenAI compatible client."""
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.0,
        max_tokens=500,
        openai_api_key=settings.deepseek_api_key,
        openai_api_base="https://api.deepseek.com/v1",
    )

    prompt = EXTRACTION_PROMPT.format(
        request_type=request_type,
        employee_code=employee_code,
        submitted_data=json.dumps(submitted_data, indent=2),
    )

    response = await llm.ainvoke(prompt)
    response_text = response.content.strip()

    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if json_match:
        result = json.loads(json_match.group())
    else:
        result = json.loads(response_text)

    # Return only updates to the state
    return {
        "extracted_variables": result,
        "confidence": float(result.get("confidence", 0.5))
    }


async def _extract_with_rules(request_type: str, submitted_data: dict) -> dict:
    """Rule-based fallback extraction."""
    result = {
        "intent": request_type,
        "category": submitted_data.get("leave_type", "annual"),
        "reason": submitted_data.get("reason", "No reason provided"),
        "confidence": 0.8
    }
    
    if "start_date" in submitted_data and "end_date" in submitted_data:
        try:
            from datetime import date as date_cls
            start = date_cls.fromisoformat(submitted_data["start_date"])
            end = date_cls.fromisoformat(submitted_data["end_date"])
            days = (end - start).days + 1
            if submitted_data.get("half_day"):
                days = 0.5
            result["days_requested"] = days
        except Exception:
            pass

    return {
        "extracted_variables": result,
        "confidence": 0.8
    }
