
# AML Alert Investigator – API Contract

## 1. Shared State

The central state is defined in app/state.py.

All graph nodes must read from AlertState and return partial state updates.

## 2. Banking Evidence Tool Contract

Every evidence tool must return a ToolResult.

Required fields:
- tool_name: str
- status: SUCCESS | UNAVAILABLE | ERROR
- source_ids: List[str]
- data: Dict[str, Any]
- error_message: Optional[str]
- execution_time_ms: float

Example:

{
    "tool_name": "transactions",
    "status": "SUCCESS",
    "source_ids": ["TX_20011", "TX_20012"],
    "data": {
        "customer_id": "CUST_1001",
        "records": []
    },
    "error_message": null,
    "execution_time_ms": 25.0
}

## 3. Evidence Storage

Evidence must be stored in:

AlertState["evidence"]

Structure:

{
    "transactions": ToolResult.model_dump(mode="json"),
    "customer_profile": ToolResult.model_dump(mode="json"),
    "watchlist": ToolResult.model_dump(mode="json")
}

Source IDs must match the identifiers used in the actual evidence records.

## 4. Policy Retrieval Contract

Policy chunks must follow this structure:

{
    "source_id": "POL_STRUCT_01",
    "title": "AML Structuring Policy",
    "content": "Retrieved policy content"
}

Store retrieved policies in:

AlertState["policy_chunks"]

## 5. Draft and Claim Validation

Draft node:
- Reads customer and transaction evidence.
- Reads retrieved policy chunks.
- Generates a case narrative.
- Includes [SRC:...] citations.

Claim check node:
- Validates citations.
- Validates source existence.
- Checks currency and date grounding.
- Checks aggregate transaction values.

Output:
- draft_note
- claims
- claim_check_passed
- redraft_count

## 6. Verification and Risk Routing

Verifier output:

- verifier_agreed
- verifier_notes
- risk_tier

Risk tiers:
- TIER_1_QUICK
- TIER_2_STANDARD
- TIER_3_FULL

## 7. Human Approval

Human review must update:

- human_approved
- human_edits
- human_notes
- reviewer_id

Investigation status must follow the defined workflow.

## 8. Final Outcome

Final workflow outputs:

- final_disposition
- status
- escalation_reason
- audit_log
- total_tokens_used
- estimated_cost_usd

## 9. Integration Rules

1. Do not rename shared state fields without team agreement.
2. Do not invent source IDs.
3. All banking evidence must preserve source IDs.
4. All graph nodes must return updates compatible with AlertState.
5. Human approval must not be bypassed.
6. All important decisions must be recorded in audit_log.
7. All tool failures must be handled explicitly.
