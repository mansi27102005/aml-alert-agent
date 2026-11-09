"""Intake and Validation Node (Role A).
Validates the incoming alert payload, standardizes entity IDs, and records intake telemetry.
"""

from datetime import datetime, timezone
from typing import Any, Dict
from app.state import AlertState, AuditEntry, InvestigationStatus


def intake_node(state: AlertState) -> Dict[str, Any]:
    """LangGraph node execution function for Alert Intake."""
    alert_id = state.get("alert_id")
    customer_id = state.get("customer_id")

    if not alert_id or not customer_id:
        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "status": InvestigationStatus.ESCALATED.value,
            "escalation_reason": "Intake validation failure: Missing alert_id or customer_id.",
            "audit_log": state.get("audit_log", []) + [
                {
                    "timestamp": now_iso,
                    "node": "intake",
                    "action": "INTAKE_VALIDATION_FAILED",
                    "details": {"error": "Missing mandatory alert identifier fields."},
                }
            ],
        }

    now_iso = datetime.now(timezone.utc).isoformat()
    audit_entry: AuditEntry = {
        "timestamp": now_iso,
        "node": "intake",
        "action": "INTAKE_VALIDATED",
        "details": {
            "alert_id": alert_id,
            "customer_id": customer_id,
            "alert_type": state.get("alert_type"),
        },
    }

    return {
        "status": InvestigationStatus.IN_PROGRESS.value,
        "audit_log": state.get("audit_log", []) + [audit_entry],
    }
