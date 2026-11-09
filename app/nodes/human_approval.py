"""Human Approval Node (Role A).
Interface for human-in-the-loop review.
Manages the state transition when an alert reaches analyst review,
and updates state when the analyst approves, edits, or overrides the disposition.
"""

from datetime import datetime, timezone
from typing import Any, Dict
from app.state import AlertState, AuditEntry, InvestigationStatus


def human_approval_node(state: AlertState) -> Dict[str, Any]:
    """LangGraph node execution function for Human Approval.
    Marks the investigation as AWAITING_APPROVAL for the Streamlit UI.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    audit_entry: AuditEntry = {
        "timestamp": now_iso,
        "node": "human_approval",
        "action": "AWAITING_HUMAN_APPROVAL",
        "details": {
            "risk_tier": state.get("risk_tier"),
            "claim_check_passed": state.get("claim_check_passed"),
            "verifier_agreed": state.get("verifier_agreed"),
        },
    }

    return {
        "status": InvestigationStatus.AWAITING_APPROVAL.value,
        "audit_log": state.get("audit_log", []) + [audit_entry],
    }


def apply_human_decision(
    state: AlertState,
    approved: bool,
    reviewer_id: str,
    edited_note: str = None,
    reviewer_comments: str = None,
    disposition_override: str = None,
) -> Dict[str, Any]:
    """Helper used by API/LangGraph resume to inject human feedback into state."""
    now_iso = datetime.now(timezone.utc).isoformat()
    audit_entry: AuditEntry = {
        "timestamp": now_iso,
        "node": "human_approval",
        "action": "HUMAN_DECISION_RECORDED",
        "details": {
            "approved": approved,
            "reviewer_id": reviewer_id,
            "has_edits": edited_note is not None,
            "disposition_override": disposition_override,
            "comments": reviewer_comments,
        },
    }

    updates: Dict[str, Any] = {
        "human_approved": approved,
        "reviewer_id": reviewer_id,
        "status": InvestigationStatus.IN_PROGRESS.value,
        "audit_log": state.get("audit_log", []) + [audit_entry],
    }
    if edited_note:
        updates["human_edits"] = edited_note
    if reviewer_comments:
        updates["human_notes"] = reviewer_comments
    if disposition_override:
        updates["final_disposition"] = disposition_override

    return updates
