"""Finalize Node (Role A).
Constructs the official FinCEN SAR Investigation Package and commits the final audit entry.
"""

from datetime import datetime, timezone
from typing import Any, Dict
from app.state import AlertState, AuditEntry, CaseDisposition, InvestigationStatus


def finalize_node(state: AlertState) -> Dict[str, Any]:
    """LangGraph node execution function for Finalize."""
    status = state.get("status")
    
    # If the case was escalated, finalize it with escalation status
    if status == InvestigationStatus.ESCALATED.value:
        final_disposition = state.get("final_disposition") or CaseDisposition.ESCALATE_L2.value
    else:
        # Completed case through human sign-off
        status = InvestigationStatus.COMPLETED.value
        
        # Determine final disposition
        if state.get("human_approved") is False:
            final_disposition = CaseDisposition.ESCALATE_L2.value
        else:
            final_disposition = state.get("final_disposition")
            if not final_disposition:
                # Infer disposition from note content
                draft = state.get("draft_note", "").lower()
                if "file sar" in draft or "file suspicious activity report" in draft:
                    final_disposition = CaseDisposition.FILE_SAR.value
                elif "request rfi" in draft or "enhanced due diligence" in draft:
                    final_disposition = CaseDisposition.REQUEST_RFI.value
                elif "false positive" in draft or "close alert" in draft:
                    final_disposition = CaseDisposition.CLOSE_FALSE_POSITIVE.value
                else:
                    final_disposition = CaseDisposition.ESCALATE_L2.value

    # Use human-edited note if analyst modified it during review
    effective_note = state.get("human_edits") or state.get("draft_note", "")

    now_iso = datetime.now(timezone.utc).isoformat()
    audit_entry: AuditEntry = {
        "timestamp": now_iso,
        "node": "finalize",
        "action": "CASE_FINALIZED",
        "details": {
            "status": status,
            "final_disposition": final_disposition,
            "human_approved": state.get("human_approved"),
            "reviewer_id": state.get("reviewer_id"),
            "total_tokens_used": state.get("total_tokens_used", 0),
            "estimated_cost_usd": state.get("estimated_cost_usd", 0.0),
        },
    }

    return {
        "status": status,
        "final_disposition": final_disposition,
        "draft_note": effective_note,
        "audit_log": state.get("audit_log", []) + [audit_entry],
    }
