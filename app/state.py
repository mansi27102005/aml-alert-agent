"""Typed shared state passed between graph nodes.
Defines the shared data contracts for the AML Alert Investigator workflow.
Conforms strictly to docs/contract.md.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict
from pydantic import BaseModel, Field


class ToolStatus(str, Enum):
    SUCCESS = "SUCCESS"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


class ToolResult(BaseModel):
    """Standard container for output from external evidence tools."""
    tool_name: str
    status: ToolStatus
    source_ids: List[str] = Field(default_factory=list, description="All source IDs provided in data")
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured factual payload")
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0


class ReviewTier(str, Enum):
    TIER_1_QUICK = "TIER_1_QUICK"       # 1-click false-positive sign-off
    TIER_2_STANDARD = "TIER_2_STANDARD" # Side-by-side evidence inspection
    TIER_3_FULL = "TIER_3_FULL"         # Mandatory full audit / SAR review


class AlertTypology(str, Enum):
    STRUCTURING = "STRUCTURING"
    SANCTIONS_MATCH = "SANCTIONS_MATCH"
    HIGH_VALUE_TRANSFER = "HIGH_VALUE_TRANSFER"
    UNKNOWN = "UNKNOWN"


class CaseDisposition(str, Enum):
    CLOSE_FALSE_POSITIVE = "CLOSE_FALSE_POSITIVE"
    FILE_SAR = "FILE_SAR"
    REQUEST_RFI = "REQUEST_RFI"
    ESCALATE_L2 = "ESCALATE_L2"


class InvestigationStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"


class ClaimItem(TypedDict):
    """Represents a single parsed sentence and its citation validation status."""
    sentence: str
    cited_source_ids: List[str]
    is_valid: bool
    validation_error: Optional[str]


class AuditEntry(TypedDict):
    """A single immutable telemetry / audit log record."""
    timestamp: str
    node: str
    action: str
    details: Dict[str, Any]


class AlertState(TypedDict):
    """The central state passed across LangGraph nodes."""
    # Alert Metadata & Payload
    alert_id: str
    alert_type: str                     # STRUCTURING, SANCTIONS_MATCH, HIGH_VALUE_TRANSFER
    customer_id: str
    raw_payload: Dict[str, Any]
    
    # RAG Context & Tools Evidence
    policy_chunks: List[Dict[str, Any]] # e.g. [{"source_id": "POL_STRUCT_01", "content": "..."}]
    evidence: Dict[str, Dict[str, Any]] # Map tool_name -> ToolResult.model_dump()
    
    # Generation & Grounding (Role A)
    draft_note: str                     # Case note narrative with [SRC:...] tags
    claims: List[ClaimItem]             # Sentence-level parsed claim ledger
    claim_check_passed: bool
    redraft_count: int                  # Max 1 redraft before circuit-breaker
    
    # Verification & Risk Routing (Role A)
    verifier_agreed: bool
    verifier_notes: str
    risk_tier: str
    
    # Human Review (HITL)
    human_approved: Optional[bool]
    human_edits: Optional[str]          # Analyst-edited note override
    human_notes: Optional[str]          # Analyst comments
    reviewer_id: Optional[str]
    
    # Final Outcome & Telemetry
    final_disposition: Optional[str]    # CaseDisposition enum value
    status: str                         # InvestigationStatus enum value
    escalation_reason: Optional[str]
    audit_log: List[AuditEntry]
    total_tokens_used: int
    estimated_cost_usd: float


def create_initial_state(alert_payload: Dict[str, Any]) -> AlertState:
    """Helper factory to construct a clean, valid initial AlertState."""
    alert_id = alert_payload.get("alert_id", "UNKNOWN_ALERT")
    customer_id = alert_payload.get("customer_id", "UNKNOWN_CUSTOMER")
    alert_type = alert_payload.get("alert_type", AlertTypology.UNKNOWN.value)
    
    now_iso = datetime.now(timezone.utc).isoformat()

    return {
        "alert_id": alert_id,
        "alert_type": alert_type,
        "customer_id": customer_id,
        "raw_payload": alert_payload,
        "policy_chunks": [],
        "evidence": {},
        "draft_note": "",
        "claims": [],
        "claim_check_passed": False,
        "redraft_count": 0,
        "verifier_agreed": False,
        "verifier_notes": "",
        "risk_tier": ReviewTier.TIER_2_STANDARD.value,
        "human_approved": None,
        "human_edits": None,
        "human_notes": None,
        "reviewer_id": None,
        "final_disposition": None,
        "status": InvestigationStatus.IN_PROGRESS.value,
        "escalation_reason": None,
        "audit_log": [
            {
                "timestamp": now_iso,
                "node": "intake",
                "action": "ALERT_INITIALIZED",
                "details": {"alert_id": alert_id, "alert_type": alert_type, "customer_id": customer_id}
            }
        ],
        "total_tokens_used": 0,
        "estimated_cost_usd": 0.0,
    }
