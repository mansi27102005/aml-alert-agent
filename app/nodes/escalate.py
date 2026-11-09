"""Escalate Node (Role A).
Circuit breaker and safe fallback handler.
Packages cases for immediate senior human investigation when:
1. Claim check still fails after one redraft.
2. Skeptical Verifier rejects the draft reasoning.
3. Execution budget (token, cost, or step limits) is exceeded.
4. Tool dropouts or unrecoverable exceptions occur.
"""

from datetime import datetime, timezone
from typing import Any, Dict
from app.state import AlertState, AuditEntry, CaseDisposition, InvestigationStatus


def escalate_node(state: AlertState) -> Dict[str, Any]:
    """LangGraph node execution function for Escalation."""
    reasons = []

    # Check known failure triggers
    if not state.get("claim_check_passed", False) and state.get("redraft_count", 0) > 1:
        reasons.append("Claim check failed after maximum redraft attempts.")

    if not state.get("verifier_agreed", True):
        reasons.append(f"Skeptical Verifier disagreed: {state.get('verifier_notes', 'Reasoning flaws detected.')}")

    for tool, data in state.get("evidence", {}).items():
        if data.get("status") != "SUCCESS":
            reasons.append(f"Evidence tool '{tool}' failed or timed out ({data.get('status')}).")

    if not reasons:
        reasons.append(state.get("escalation_reason") or "Manual or circuit-breaker escalation triggered.")

    consolidated_reason = " | ".join(reasons)

    now_iso = datetime.now(timezone.utc).isoformat()
    audit_entry: AuditEntry = {
        "timestamp": now_iso,
        "node": "escalate",
        "action": "ALERT_ESCALATED",
        "details": {
            "escalation_reasons": reasons,
            "redraft_count": state.get("redraft_count", 0),
            "total_tokens_used": state.get("total_tokens_used", 0),
            "estimated_cost_usd": state.get("estimated_cost_usd", 0.0),
        },
    }

    return {
        "status": InvestigationStatus.ESCALATED.value,
        "final_disposition": CaseDisposition.ESCALATE_L2.value,
        "escalation_reason": consolidated_reason,
        "audit_log": state.get("audit_log", []) + [audit_entry],
    }
