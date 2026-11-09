"""Audit and telemetry logger for AML Alert Investigator (Role A).
Provides immutable event logging, token and cost accounting, and audit export.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
from app.state import AlertState, AuditEntry


# Approximate pricing per 1M tokens for popular enterprise models
MODEL_PRICING = {
    "gemini-1.5-flash": {"input_per_m": 0.075, "output_per_m": 0.30},
    "gemini-1.5-pro": {"input_per_m": 1.25, "output_per_m": 5.00},
    "gpt-4o-mini": {"input_per_m": 0.15, "output_per_m": 0.60},
    "gpt-4o": {"input_per_m": 2.50, "output_per_m": 10.00},
    "default": {"input_per_m": 0.15, "output_per_m": 0.60},
}


def calculate_token_cost(input_tokens: int, output_tokens: int, model_name: str = "default") -> float:
    """Calculates estimated USD cost for model token consumption."""
    pricing = MODEL_PRICING.get(model_name.lower(), MODEL_PRICING["default"])
    input_cost = (input_tokens / 1_000_000.0) * pricing["input_per_m"]
    output_cost = (output_tokens / 1_000_000.0) * pricing["output_per_m"]
    return round(input_cost + output_cost, 6)


def record_audit_event(
    state: AlertState,
    node: str,
    action: str,
    details: Dict[str, Any],
) -> List[AuditEntry]:
    """Creates a new immutable AuditEntry and returns the updated audit log list."""
    now_iso = datetime.now(timezone.utc).isoformat()
    entry: AuditEntry = {
        "timestamp": now_iso,
        "node": node,
        "action": action,
        "details": details,
    }
    current_log = list(state.get("audit_log", []))
    current_log.append(entry)
    return current_log


def export_audit_trail_json(audit_log: List[AuditEntry], indent: int = 2) -> str:
    """Serializes the audit trail to a formatted JSON string for persistence or compliance review."""
    return json.dumps(audit_log, indent=indent, default=str)
