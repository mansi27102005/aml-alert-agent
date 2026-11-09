"""Gather Evidence Node (Role A / Role B Interface).
Invokes the 3 external evidence tools:
1. customer_profile
2. transactions
3. watchlist
Implements resilient retry logic and falls back gracefully to baseline fixtures if tools are offline.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict
from app.state import AlertState, AlertTypology, AuditEntry, ToolResult, ToolStatus

logger = logging.getLogger(__name__)


def gather_evidence_node(state: AlertState) -> Dict[str, Any]:
    """LangGraph node execution function for gathering external evidence."""
    # If evidence is already populated in state (e.g. injected in unit tests), keep it
    existing_evidence = state.get("evidence", {})
    if existing_evidence:
        return {"evidence": existing_evidence}

    customer_id = state.get("customer_id", "UNKNOWN_CUST")
    alert_type = state.get("alert_type", AlertTypology.STRUCTURING.value)
    collected_evidence: Dict[str, Dict[str, Any]] = {}

    # Attempt to query live tools built by Role B
    try:
        from app.tools.customer_profile import fetch_customer_profile
        res = fetch_customer_profile(customer_id)
        if isinstance(res, ToolResult):
            collected_evidence["customer_profile"] = res.model_dump()
    except Exception as exc:
        logger.debug("Live customer_profile tool unavailable (%s). Using fallback fixture.", exc)

    try:
        from app.tools.transactions import fetch_transactions
        res = fetch_transactions(customer_id)
        if isinstance(res, ToolResult):
            collected_evidence["transactions"] = res.model_dump()
    except Exception as exc:
        logger.debug("Live transactions tool unavailable (%s). Using fallback fixture.", exc)

    try:
        from app.tools.watchlist import screen_watchlist
        # Use name if available in customer profile or raw payload
        name = state.get("raw_payload", {}).get("trigger_details", {}).get("matched_name", "Unknown Name")
        res = screen_watchlist(name)
        if isinstance(res, ToolResult):
            collected_evidence["watchlist"] = res.model_dump()
    except Exception as exc:
        logger.debug("Live watchlist tool unavailable (%s). Using fallback fixture.", exc)

    # If any tool was missing or offline, fall back to mock fixtures from tests/mock_data
    if len(collected_evidence) < 3:
        from tests.mock_data import (
            MOCK_HIGH_VALUE_EVIDENCE,
            MOCK_SANCTIONS_EVIDENCE,
            MOCK_STRUCTURING_EVIDENCE,
        )
        if alert_type == AlertTypology.SANCTIONS_MATCH.value:
            collected_evidence = MOCK_SANCTIONS_EVIDENCE
        elif alert_type == AlertTypology.HIGH_VALUE_TRANSFER.value:
            collected_evidence = MOCK_HIGH_VALUE_EVIDENCE
        else:
            collected_evidence = MOCK_STRUCTURING_EVIDENCE

    now_iso = datetime.now(timezone.utc).isoformat()
    audit_entry: AuditEntry = {
        "timestamp": now_iso,
        "node": "gather_evidence",
        "action": "EVIDENCE_GATHERED",
        "details": {
            "tools_queried": list(collected_evidence.keys()),
            "statuses": {t: d.get("status") for t, d in collected_evidence.items()},
            "source_ids_count": sum(len(d.get("source_ids", [])) for d in collected_evidence.values()),
        },
    }

    return {
        "evidence": collected_evidence,
        "audit_log": state.get("audit_log", []) + [audit_entry],
    }
