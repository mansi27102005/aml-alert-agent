
"""Finalize Node (Role A).

Handles analyst approval, disposition overrides,
human-edited narratives and final audit logging.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from app.state import (
    AlertState,
    AuditEntry,
    CaseDisposition,
    InvestigationStatus,
)


def finalize_node(state: AlertState) -> Dict[str, Any]:
    """Finalize an investigation after an explicit human decision."""

    current_status = state.get("status")
    human_approved = state.get("human_approved")

    # Preserve cases already escalated by automated controls.
    if current_status == InvestigationStatus.ESCALATED.value:
        final_status = InvestigationStatus.ESCALATED.value
        final_disposition = (
            state.get("final_disposition")
            or CaseDisposition.ESCALATE_L2.value
        )

    else:
        # Never finalize without an explicit human decision.
        if human_approved is None:
            raise ValueError(
                "Human approval is required before finalization."
            )

        # Analyst rejection always results in escalation.
        if human_approved is False:
            final_status = InvestigationStatus.ESCALATED.value
            final_disposition = CaseDisposition.ESCALATE_L2.value

        else:
            final_status = InvestigationStatus.COMPLETED.value

            # Read the existing disposition, if supplied.
            final_disposition = state.get("final_disposition")

            valid_dispositions = {
                item.value for item in CaseDisposition
            }

            # Discard invalid disposition values.
            if final_disposition not in valid_dispositions:
                final_disposition = None

            # Infer disposition only if no valid value exists.
            if final_disposition is None:

                # Define this variable before checking any phrases.
                review_text = " ".join([
                    str(state.get("draft_note") or ""),
                    str(state.get("human_edits") or ""),
                    str(state.get("human_notes") or ""),
                ]).lower().replace("_", " ")

                if any(phrase in review_text for phrase in [
                    "recommend sar filing",
                    "recommend filing sar",
                    "file sar",
                    "file suspicious activity report",
                ]):
                    final_disposition = (
                        CaseDisposition.FILE_SAR.value
                    )

                elif any(phrase in review_text for phrase in [
                    "request rfi",
                    "request further information",
                    "enhanced due diligence",
                ]):
                    final_disposition = (
                        CaseDisposition.REQUEST_RFI.value
                    )

                elif any(phrase in review_text for phrase in [
                    "false positive",
                    "close alert",
                    "close false positive",
                ]):
                    final_disposition = (
                        CaseDisposition.CLOSE_FALSE_POSITIVE.value
                    )

                else:
                    final_disposition = (
                        CaseDisposition.ESCALATE_L2.value
                    )

    # Preserve the analyst-edited narrative.
    effective_note = (
        state.get("human_edits")
        or state.get("draft_note", "")
    )

    # Append final audit event.
    now_iso = datetime.now(timezone.utc).isoformat()

    audit_entry: AuditEntry = {
        "timestamp": now_iso,
        "node": "finalize",
        "action": "CASE_FINALIZED",
        "details": {
            "status": final_status,
            "final_disposition": final_disposition,
            "human_approved": human_approved,
            "reviewer_id": state.get("reviewer_id"),
            "reviewer_comments": state.get("human_notes"),
            "human_edits_applied": bool(state.get("human_edits")),
            "total_tokens_used": state.get("total_tokens_used", 0),
            "estimated_cost_usd": state.get(
                "estimated_cost_usd", 0.0
            ),
        },
    }

    return {
        "status": final_status,
        "final_disposition": final_disposition,
        "draft_note": effective_note,
        "audit_log": state.get("audit_log", []) + [audit_entry],
    }
