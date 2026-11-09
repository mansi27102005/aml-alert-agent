"""Retrieve Policy Node (Role A / Role B Interface).
Retrieves relevant AML policy chunks via ChromaDB RAG.
Gracefully falls back to baseline policy fixtures if RAG vector DB is offline.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List
from app.state import AlertState, AlertTypology, AuditEntry

logger = logging.getLogger(__name__)


def retrieve_policy_node(state: AlertState) -> Dict[str, Any]:
    """LangGraph node execution function for Policy Retrieval."""
    # If policy chunks are already provided in state, retain them
    existing_chunks = state.get("policy_chunks", [])
    if existing_chunks:
        return {"policy_chunks": existing_chunks}

    alert_type = state.get("alert_type", AlertTypology.STRUCTURING.value)
    retrieved_chunks: List[Dict[str, Any]] = []

    # Attempt to query live RAG pipeline from Role B if available
    try:
        from app.rag.retrieve import retrieve_policy_context
        retrieved_chunks = retrieve_policy_context(
            query=f"AML policy requirements for {alert_type}",
            typology=alert_type,
            top_k=2,
        )
    except Exception as exc:
        logger.debug("Live RAG lookup unavailable (%s). Using baseline policy knowledge.", exc)

    # Robust fallback to baseline institutional policy chunks
    if not retrieved_chunks:
        if alert_type == AlertTypology.SANCTIONS_MATCH.value:
            retrieved_chunks = [
                {
                    "source_id": "POL_SANCT_01",
                    "title": "AML-02: OFAC and International Sanctions Compliance",
                    "content": (
                        "Financial institutions are subject to strict liability under OFAC regulations. "
                        "Any confirmed match or high-probability fuzzy match (score >= 80%) against the "
                        "OFAC Specially Designated Nationals (SDN) or PEP lists requires immediate freezing "
                        "of assets and escalation to the Designated Sanctions Officer. Automated closure is strictly prohibited."
                    ),
                }
            ]
        elif alert_type == AlertTypology.HIGH_VALUE_TRANSFER.value:
            retrieved_chunks = [
                {
                    "source_id": "POL_HVT_01",
                    "title": "AML-03: Unusual High-Value Transaction Monitoring",
                    "content": (
                        "Transactions exceeding $100,000 must be reviewed against customer expected profile. "
                        "If transaction rationale is documented (e.g. licensed real estate purchase or verified escrow) "
                        "and customer net worth supports the volume, the alert may be closed as a false positive "
                        "with Level 1 supervisor concurrence."
                    ),
                }
            ]
        else:
            retrieved_chunks = [
                {
                    "source_id": "POL_STRUCT_01",
                    "title": "AML-01: Currency Transaction Reporting and Structuring",
                    "content": (
                        "Under 31 CFR § 1010.311 and BSA regulations, financial institutions must report "
                        "currency transactions exceeding $10,000. Structuring is the intentional conduct of "
                        "multiple currency transactions below $10,000 within 5 business days to evade reporting. "
                        "If aggregate deposits exceed $10,000 across multiple sub-threshold transactions with no "
                        "clear economic rationale, an investigation must be escalated and a SAR considered."
                    ),
                }
            ]

    now_iso = datetime.now(timezone.utc).isoformat()
    audit_entry: AuditEntry = {
        "timestamp": now_iso,
        "node": "retrieve_policy",
        "action": "POLICIES_RETRIEVED",
        "details": {
            "chunk_count": len(retrieved_chunks),
            "source_ids": [c.get("source_id") for c in retrieved_chunks],
        },
    }

    return {
        "policy_chunks": retrieved_chunks,
        "audit_log": state.get("audit_log", []) + [audit_entry],
    }
