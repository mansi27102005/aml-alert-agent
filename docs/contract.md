# Interface Contract v1.0
**Shared specification between Role A (Agent & Trust Core) and Role B (Data, Platform & Demo)**

> **Policy:** Changes to this contract must be agreed upon by both team members before editing code.

---

## 1. Source ID Conventions

Every piece of evidence and retrieved policy chunk must have a globally unique, deterministic Source ID format.

| Data Type | ID Format | Example | Source Generator |
| :--- | :--- | :--- | :--- |
| **Policy Chunk** | `POL_<TYPOLOGY>_<CHUNK_NUM>` | `POL_STRUCT_01`, `POL_SANCT_02` | `app/rag/retrieve.py` [Role B] |
| **Customer KYC** | `CUST_<ID>_<FIELD>` | `CUST_C104_KYC`, `CUST_C104_OCCUPATION` | `app/tools/customer_profile.py` [Role B] |
| **Transaction Record** | `TX_<TX_ID>` | `TX_8841`, `TX_8842` | `app/tools/transactions.py` [Role B] |
| **Watchlist Screening** | `WL_<HIT_OR_CLEAN>_<ID>` | `WL_HIT_OFAC_01`, `WL_CLEAN_C104` | `app/tools/watchlist.py` [Role B] |

---

## 2. Tool Signatures & Return Schema

All tools in `app/tools/` must adhere strictly to these principles:
1. **Never throw uncaught exceptions:** Catch internal errors (e.g. timeout, file missing) and return a failed `ToolResult`.
2. **Deterministic return type:** Always return an instance of `ToolResult`.

```python
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from enum import Enum

class ToolStatus(str, Enum):
    SUCCESS = "SUCCESS"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"

class ToolResult(BaseModel):
    tool_name: str
    status: ToolStatus
    source_ids: List[str] = Field(default_factory=list, description="All source IDs provided in data")
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured factual payload")
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
```

### Tool Signatures:
- `fetch_customer_profile(customer_id: str) -> ToolResult`
- `fetch_transactions(customer_id: str, lookback_days: int = 90) -> ToolResult`
- `screen_watchlist(customer_name: str, dob: Optional[str] = None, country: Optional[str] = None) -> ToolResult`

---

## 3. LangGraph State Schema (`app/state.py`)

This state is shared across all nodes in the state machine:

```python
from typing import TypedDict, List, Dict, Any, Optional
from enum import Enum

class ReviewTier(str, Enum):
    TIER_1_QUICK = "TIER_1_QUICK"       # 1-click false-positive sign-off
    TIER_2_STANDARD = "TIER_2_STANDARD" # Side-by-side evidence inspection
    TIER_3_FULL = "TIER_3_FULL"         # Mandatory full audit / SAR review

class ClaimItem(TypedDict):
    sentence: str
    cited_source_ids: List[str]
    is_valid: bool
    validation_error: Optional[str]

class AlertState(TypedDict):
    # Alert Metadata
    alert_id: str
    alert_type: str                     # "STRUCTURING", "SANCTIONS_MATCH", "HIGH_VALUE_TRANSFER"
    customer_id: str
    raw_payload: Dict[str, Any]
    
    # RAG Context & Tools Evidence
    policy_chunks: List[Dict[str, Any]] # e.g. [{"source_id": "POL_STRUCT_01", "content": "..."}]
    evidence: Dict[str, Dict[str, Any]] # Map tool_name -> ToolResult.model_dump()
    
    # Generation & Grounding (Role A)
    draft_note: str                     # Sentences with [SRC:...] tokens
    claims: List[ClaimItem]             # Extracted sentence citations
    claim_check_passed: bool
    redraft_count: int                  # Max 1 redraft before escalation
    
    # Verification & Risk Routing (Role A)
    verifier_agreed: bool
    verifier_notes: str
    risk_tier: ReviewTier
    
    # Human Review (Streamlit HITL - Role B / LangGraph interrupt - Role A)
    human_approved: Optional[bool]
    human_edits: Optional[str]          # Analyst-edited final note
    human_notes: Optional[str]          # Analyst comments
    reviewer_id: Optional[str]
    
    # Final Outcome & Telemetry
    final_disposition: Optional[str]    # "CLOSE_FALSE_POSITIVE", "FILE_SAR", "REQUEST_RFI", "ESCALATE_L2"
    status: str                         # "IN_PROGRESS", "AWAITING_APPROVAL", "COMPLETED", "ESCALATED"
    escalation_reason: Optional[str]
    audit_log: List[Dict[str, Any]]     # Timestamped event trace
    total_tokens_used: int
    estimated_cost_usd: float
```

---

## 4. API Request & Response Shapes (`app/api.py`)

FastAPI exposes these endpoints for the UI or automated test runners:

### `POST /alerts/investigate`
* **Request:**
  ```json
  {
    "alert_id": "ALT-2026-001",
    "alert_type": "STRUCTURING",
    "customer_id": "CUST-1049",
    "trigger_details": {
      "transaction_ids": ["TX-901", "TX-902", "TX-903"],
      "total_amount": 28500.0,
      "time_window_hours": 72
    }
  }
  ```
* **Response (Awaiting HITL):**
  ```json
  {
    "alert_id": "ALT-2026-001",
    "status": "AWAITING_APPROVAL",
    "risk_tier": "TIER_2_STANDARD",
    "draft_note": "Customer conducted 3 transactions totaling $28,500 over 72 hours [SRC:TX_901, TX_902, TX_903]...",
    "claims": [
      {
        "sentence": "Customer conducted 3 transactions totaling $28,500 over 72 hours.",
        "cited_source_ids": ["TX_901", "TX_902", "TX_903"],
        "is_valid": true,
        "validation_error": null
      }
    ],
    "verifier_agreed": true,
    "evidence_summary": {
      "customer_profile": "SUCCESS",
      "transactions": "SUCCESS",
      "watchlist": "SUCCESS"
    }
  }
  ```

### `POST /alerts/{alert_id}/approve`
* **Request:**
  ```json
  {
    "reviewer_id": "analyst_sarah_m",
    "approved": true,
    "disposition_override": null,
    "edited_note": null,
    "reviewer_comments": "Verified transactions against commercial supplier invoices. False positive."
  }
  ```
* **Response (Completed):**
  ```json
  {
    "alert_id": "ALT-2026-001",
    "status": "COMPLETED",
    "final_disposition": "CLOSE_FALSE_POSITIVE",
    "audit_event_count": 14
  }
  ```

### `GET /alerts/{alert_id}/state`
* Returns full current `AlertState` dictionary for inspection.

---

## 5. Development Decoupling (Mock Data Protocol)

To allow **Role A** and **Role B** to build concurrently without blocking:
1. **Mock Fixture:** Role B creates a static `tests/mock_evidence.json` matching the `ToolResult` format on Day 1.
2. **Offline Graph Testing:** Role A uses `tests/mock_evidence.json` to test `gather_evidence`, `draft_note`, `claim_check`, `verifier`, and `risk_router` without waiting for real ChromaDB or database tools.
3. **Mock Graph API:** Role A provides a stubbed graph response so Role B can wire the Streamlit UI and FastAPI endpoints without waiting for LLM prompts to be tuned.

