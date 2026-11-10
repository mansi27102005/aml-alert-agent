"""Realistic mock fixtures for Role A unit and integration testing.
Simulates tool outputs, RAG policy chunks, and alert payloads for all 3 typologies:
1. Structuring (Smurfing sub-threshold cash deposits)
2. Sanctions / Watchlist fuzzy match
3. Unusual High-Value Transfer (Legitimate commercial escrow)
"""

import copy
from typing import Any, Dict, List
from app.state import (
    AlertState,
    AlertTypology,
    CaseDisposition,
    ReviewTier,
    ToolResult,
    ToolStatus,
    create_initial_state,
)

# ============================================================================
# 1. STRUCTURING ALERT FIXTURES
# ============================================================================

MOCK_STRUCTURING_PAYLOAD = {
    "alert_id": "ALT-STR-001",
    "alert_type": AlertTypology.STRUCTURING.value,
    "customer_id": "CUST-1049",
    "trigger_details": {
        "transaction_ids": ["TX-8801", "TX-8802", "TX-8803", "TX-8804"],
        "total_amount": 38100.0,
        "time_window_hours": 72,
    },
}

MOCK_STRUCTURING_POLICY_CHUNKS: List[Dict[str, Any]] = [
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

MOCK_STRUCTURING_EVIDENCE: Dict[str, Dict[str, Any]] = {
    "customer_profile": ToolResult(
        tool_name="customer_profile",
        status=ToolStatus.SUCCESS,
        source_ids=["CUST_1049_KYC", "CUST_1049_OCCUPATION"],
        data={
            "customer_id": "CUST-1049",
            "full_name": "Alex Rivera",
            "occupation": "Retail Cashier",
            "monthly_income": 3000.0,
            "annual_income": 36000.0,
            "kyc_risk_rating": "LOW",
            "account_opened_date": "2024-03-15",
        },
    ).model_dump(mode="json"),
    "transactions": ToolResult(
        tool_name="transactions",
        status=ToolStatus.SUCCESS,
        source_ids=["TX_8801", "TX_8802", "TX_8803", "TX_8804"],
        data={
            "customer_id": "CUST-1049",
            "lookback_days": 30,
            "transaction_count": 4,
            "total_volume": 38100.0,
            "records": [
                {
                    "tx_id": "TX_8801",
                    "date": "2026-10-12",
                    "amount": 9500.0,
                    "type": "CASH_DEPOSIT",
                    "memo": "Branch cash deposit ATM 12",
                },
                {
                    "tx_id": "TX_8802",
                    "date": "2026-10-13",
                    "amount": 9400.0,
                    "type": "CASH_DEPOSIT",
                    "memo": "Branch cash deposit ATM 14",
                },
                {
                    "tx_id": "TX_8803",
                    "date": "2026-10-13",
                    "amount": 9600.0,
                    "type": "CASH_DEPOSIT",
                    "memo": "Branch teller cash deposit",
                },
                {
                    "tx_id": "TX_8804",
                    "date": "2026-10-14",
                    "amount": 9600.0,
                    "type": "CASH_DEPOSIT",
                    "memo": "Branch cash deposit ATM 03",
                },
            ],
        },
    ).model_dump(mode="json"),
    "watchlist": ToolResult(
        tool_name="watchlist",
        status=ToolStatus.SUCCESS,
        source_ids=["WL_CLEAN_1049"],
        data={
            "customer_id": "CUST-1049",
            "query_name": "Alex Rivera",
            "match_found": False,
            "highest_similarity_score": 12.0,
            "matched_entries": [],
        },
    ).model_dump(mode="json"),
}

VALID_STRUCTURING_DRAFT = (
    "Customer Alex Rivera is employed as a Retail Cashier with a stated annual income of $36,000 [SRC:CUST_1049_KYC, CUST_1049_OCCUPATION]. "
    "Between 2026-10-12 and 2026-10-14, four cash deposits totaling $38,100 were executed in sub-threshold amounts [SRC:TX_8801, TX_8802, TX_8803, TX_8804]. "
    "The repeated cash deposits below $10,000 with no documented commercial origin indicate potential structuring to evade CTR requirements [SRC:POL_STRUCT_01]. "
    "No watchlist or sanctions matches were identified for this customer [SRC:WL_CLEAN_1049]. "
    "Recommendation: File Suspicious Activity Report (SAR) due to suspected structuring [SRC:POL_STRUCT_01]."
)


# ============================================================================
# 2. SANCTIONS ALERT FIXTURES
# ============================================================================

MOCK_SANCTIONS_PAYLOAD = {
    "alert_id": "ALT-SAN-002",
    "alert_type": AlertTypology.SANCTIONS_MATCH.value,
    "customer_id": "CUST-2055",
    "trigger_details": {
        "transaction_ids": ["TX-9105"],
        "total_amount": 15000.0,
        "matched_name": "Tariq Al-Mansoor",
    },
}

MOCK_SANCTIONS_POLICY_CHUNKS: List[Dict[str, Any]] = [
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

MOCK_SANCTIONS_EVIDENCE: Dict[str, Dict[str, Any]] = {
    "customer_profile": ToolResult(
        tool_name="customer_profile",
        status=ToolStatus.SUCCESS,
        source_ids=["CUST_2055_KYC", "CUST_2055_NATIONALITY"],
        data={
            "customer_id": "CUST-2055",
            "full_name": "Tariq Al-Mansoor",
            "dob": "1982-04-15",
            "country": "Syria",
            "occupation": "Import Export General Trading",
            "kyc_risk_rating": "HIGH",
        },
    ).model_dump(mode="json"),
    "transactions": ToolResult(
        tool_name="transactions",
        status=ToolStatus.SUCCESS,
        source_ids=["TX_9105"],
        data={
            "customer_id": "CUST-2055",
            "records": [
                {
                    "tx_id": "TX_9105",
                    "date": "2026-11-01",
                    "amount": 15000.0,
                    "type": "OUTGOING_WIRE",
                    "counterparty": "Levant Maritime Logistics LLC",
                    "memo": "Parts shipment logistics",
                }
            ],
        },
    ).model_dump(mode="json"),
    "watchlist": ToolResult(
        tool_name="watchlist",
        status=ToolStatus.SUCCESS,
        source_ids=["WL_HIT_OFAC_01"],
        data={
            "customer_id": "CUST-2055",
            "query_name": "Tariq Al-Mansoor",
            "match_found": True,
            "highest_similarity_score": 94.5,
            "matched_entries": [
                {
                    "entity_id": "OFAC-SDN-10992",
                    "name": "Tariq Al-Mansour",
                    "dob": "1982-04-15",
                    "nationality": "Syria",
                    "list": "OFAC_SDN",
                    "match_score": 94.5,
                }
            ],
        },
    ).model_dump(mode="json"),
}


# ============================================================================
# 3. HIGH-VALUE TRANSFER FIXTURES (False Positive / Commercial Escrow)
# ============================================================================

MOCK_HIGH_VALUE_PAYLOAD = {
    "alert_id": "ALT-HVT-003",
    "alert_type": AlertTypology.HIGH_VALUE_TRANSFER.value,
    "customer_id": "CUST-3088",
    "trigger_details": {
        "transaction_ids": ["TX-9940"],
        "total_amount": 250000.0,
    },
}

MOCK_HIGH_VALUE_POLICY_CHUNKS: List[Dict[str, Any]] = [
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

MOCK_HIGH_VALUE_EVIDENCE: Dict[str, Dict[str, Any]] = {
    "customer_profile": ToolResult(
        tool_name="customer_profile",
        status=ToolStatus.SUCCESS,
        source_ids=["CUST_3088_KYC", "CUST_3088_NETWORTH"],
        data={
            "customer_id": "CUST-3088",
            "full_name": "Dr. Elena Rostova",
            "occupation": "Chief of Neurosurgery",
            "annual_income": 450000.0,
            "kyc_risk_rating": "LOW",
        },
    ).model_dump(mode="json"),
    "transactions": ToolResult(
        tool_name="transactions",
        status=ToolStatus.SUCCESS,
        source_ids=["TX_9940"],
        data={
            "customer_id": "CUST-3088",
            "records": [
                {
                    "tx_id": "TX_9940",
                    "date": "2026-10-25",
                    "amount": 250000.0,
                    "type": "OUTGOING_WIRE",
                    "counterparty": "First American Title & Escrow Co",
                    "memo": "Escrow deposit - 42 Elm St Commercial Purchase",
                }
            ],
        },
    ).model_dump(mode="json"),
    "watchlist": ToolResult(
        tool_name="watchlist",
        status=ToolStatus.SUCCESS,
        source_ids=["WL_CLEAN_3088"],
        data={
            "customer_id": "CUST-3088",
            "query_name": "Elena Rostova",
            "match_found": False,
            "highest_similarity_score": 8.0,
            "matched_entries": [],
        },
    ).model_dump(mode="json"),
}


# ============================================================================
# HELPER GENERATOR FOR TESTS
# ============================================================================

def get_mock_alert_state(alert_type: str = AlertTypology.STRUCTURING.value) -> AlertState:
    """Returns a fully populated, deep-copied AlertState ready for node execution."""
    if alert_type == AlertTypology.SANCTIONS_MATCH.value:
        state = create_initial_state(MOCK_SANCTIONS_PAYLOAD)
        state["policy_chunks"] = copy.deepcopy(MOCK_SANCTIONS_POLICY_CHUNKS)
        state["evidence"] = copy.deepcopy(MOCK_SANCTIONS_EVIDENCE)
    elif alert_type == AlertTypology.HIGH_VALUE_TRANSFER.value:
        state = create_initial_state(MOCK_HIGH_VALUE_PAYLOAD)
        state["policy_chunks"] = copy.deepcopy(MOCK_HIGH_VALUE_POLICY_CHUNKS)
        state["evidence"] = copy.deepcopy(MOCK_HIGH_VALUE_EVIDENCE)
    else:
        state = create_initial_state(MOCK_STRUCTURING_PAYLOAD)
        state["policy_chunks"] = copy.deepcopy(MOCK_STRUCTURING_POLICY_CHUNKS)
        state["evidence"] = copy.deepcopy(MOCK_STRUCTURING_EVIDENCE)

    return state
