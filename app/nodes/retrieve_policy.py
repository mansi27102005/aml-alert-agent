
"""Retrieve Policy Node (Role A / Role B Interface).
Retrieves AML policy chunks using ChromaDB RAG.
Validates policy source IDs against the alert typology.
Falls back to baseline policy fixtures when RAG is unavailable
or returns irrelevant policy chunks.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List

from app.state import AlertState, AlertTypology, AuditEntry

logger = logging.getLogger(__name__)

POLICY_BY_TYPOLOGY = {
    AlertTypology.STRUCTURING.value: "POL_STRUCT_01",
    AlertTypology.SANCTIONS_MATCH.value: "POL_SANCT_01",
    AlertTypology.HIGH_VALUE_TRANSFER.value: "POL_HVT_01",
}

BASELINE_POLICIES = {
    "POL_STRUCT_01": {
        "source_id": "POL_STRUCT_01",
        "title": "AML-01: Currency Transaction Reporting and Structuring",
        "content": (
            "Under 31 CFR § 1010.311 and BSA regulations, financial "
            "institutions must report currency transactions exceeding "
            "$10,000. Structuring is the intentional conduct of multiple "
            "currency transactions below $10,000 within 5 business days "
            "to evade reporting. If aggregate deposits exceed $10,000 "
            "across multiple sub-threshold transactions with no clear "
            "economic rationale, an investigation must be escalated "
            "and a SAR considered."
        ),
    },
    "POL_SANCT_01": {
        "source_id": "POL_SANCT_01",
        "title": "AML-02: OFAC and International Sanctions Compliance",
        "content": (
            "Financial institutions are subject to strict liability under "
            "OFAC regulations. Any confirmed match or high-probability "
            "fuzzy match (score >= 80%) against the OFAC Specially "
            "Designated Nationals (SDN) or PEP lists requires immediate "
            "freezing of assets and escalation to the Designated "
            "Sanctions Officer. Automated closure is strictly prohibited."
        ),
    },
    "POL_HVT_01": {
        "source_id": "POL_HVT_01",
        "title": "AML-03: Unusual High-Value Transaction Monitoring",
        "content": (
            "Transactions exceeding $100,000 must be reviewed against "
            "the customer expected profile. If transaction rationale "
            "is documented and customer net worth supports the volume, "
            "the alert may be closed as a false positive with "
            "Level 1 supervisor concurrence."
        ),
    },
}


def retrieve_policy_node(state: AlertState) -> Dict[str, Any]:

    alert_type = state.get(
        "alert_type",
        AlertTypology.STRUCTURING.value,
    )

    expected_source = POLICY_BY_TYPOLOGY.get(
        alert_type,
        "POL_STRUCT_01",
    )

    # 1. Check any previously supplied policy chunks.
    existing_chunks = state.get("policy_chunks", [])

    valid_existing = [
        chunk for chunk in existing_chunks
        if chunk.get("source_id") == expected_source
    ]

    if valid_existing:
        return {"policy_chunks": valid_existing}

    # 2. Attempt live ChromaDB retrieval.
    retrieved_chunks: List[Dict[str, Any]] = []

    try:
        from app.rag.retrieve import retrieve_policy_context

        results = retrieve_policy_context(
            query=f"AML policy requirements for {alert_type}",
            typology=alert_type,
            top_k=5,
        )

        # Never accept a policy belonging to another typology.
        retrieved_chunks = [
            chunk for chunk in results
            if chunk.get("source_id") == expected_source
        ]

        if results and not retrieved_chunks:
            logger.warning(
                "RAG returned irrelevant policies for %s. "
                "Expected source: %s",
                alert_type,
                expected_source,
            )

    except Exception as exc:
        logger.warning(
            "RAG retrieval failed: %s",
            exc,
        )

    # 3. Use the correct baseline policy if needed.
    if not retrieved_chunks:
        retrieved_chunks = [BASELINE_POLICIES[expected_source]]

        logger.info(
            "Using baseline policy: %s",
            expected_source,
        )

    # 4. Audit logging.
    now_iso = datetime.now(timezone.utc).isoformat()

    audit_entry: AuditEntry = {
        "timestamp": now_iso,
        "node": "retrieve_policy",
        "action": "POLICIES_RETRIEVED",
        "details": {
            "alert_type": alert_type,
            "expected_source": expected_source,
            "chunk_count": len(retrieved_chunks),
            "source_ids": [
                chunk.get("source_id")
                for chunk in retrieved_chunks
            ],
        },
    }

    return {
        "policy_chunks": retrieved_chunks,
        "audit_log": (
            state.get("audit_log", []) + [audit_entry]
        ),
    }
