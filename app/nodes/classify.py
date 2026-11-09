"""Classify Node (Role A).
Uses LLM reasoning to categorize raw incoming alerts into one of 3 AML typologies:
STRUCTURING, SANCTIONS_MATCH, or HIGH_VALUE_TRANSFER.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict
from app.audit import calculate_token_cost
from app.config import settings
from app.llm import call_llm
from app.state import AlertState, AlertTypology, AuditEntry

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "classify.txt"


def classify_node(state: AlertState) -> Dict[str, Any]:
    """LangGraph node execution function for Classify."""
    # If alert_type is already known and valid from intake, skip or confirm
    current_type = state.get("alert_type")
    if current_type and current_type in [
        AlertTypology.STRUCTURING.value,
        AlertTypology.SANCTIONS_MATCH.value,
        AlertTypology.HIGH_VALUE_TRANSFER.value,
    ]:
        return {"alert_type": current_type}

    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    alert_payload = state.get("raw_payload", {})
    prompt = prompt_template.format(alert_payload=json.dumps(alert_payload, indent=2))

    response_text, in_tok, out_tok = call_llm(prompt, json_mode=True)
    call_cost = calculate_token_cost(in_tok, out_tok, settings.LLM_MODEL)

    # Parse classification JSON
    classified_type = AlertTypology.STRUCTURING.value
    confidence = 0.5
    reasoning = ""

    try:
        data = json.loads(response_text)
        classified_type = data.get("typology", classified_type)
        confidence = float(data.get("confidence", confidence))
        reasoning = data.get("reasoning", "")
    except Exception:
        # Fallback keyword heuristics if JSON parsing fails
        lower = response_text.lower()
        if "sanct" in lower or "ofac" in lower:
            classified_type = AlertTypology.SANCTIONS_MATCH.value
        elif "high_value" in lower or "transfer" in lower:
            classified_type = AlertTypology.HIGH_VALUE_TRANSFER.value

    now_iso = datetime.now(timezone.utc).isoformat()
    audit_entry: AuditEntry = {
        "timestamp": now_iso,
        "node": "classify",
        "action": "ALERT_CLASSIFIED",
        "details": {
            "classified_typology": classified_type,
            "confidence": confidence,
            "reasoning": reasoning,
            "tokens_used": in_tok + out_tok,
            "cost_usd": call_cost,
        },
    }

    return {
        "alert_type": classified_type,
        "total_tokens_used": state.get("total_tokens_used", 0) + in_tok + out_tok,
        "estimated_cost_usd": state.get("estimated_cost_usd", 0.0) + call_cost,
        "audit_log": state.get("audit_log", []) + [audit_entry],
    }
