"""Unit tests for the Deterministic Risk Router Node (Role A).
Verifies:
1. Routing to TIER_3_FULL on sanctions hits, high volume, missing tools, or redrafts.
2. Routing to TIER_1_QUICK on verified, low-value, low-risk false positives.
3. Routing to TIER_2_STANDARD on intermediate business scenarios.
4. Correct audit trail logging.
"""

import pytest
from app.nodes.risk_router import risk_router_node
from app.state import AlertTypology, ReviewTier, ToolStatus
from tests.mock_data import get_mock_alert_state


def test_risk_router_sanctions_hit_routes_to_tier_3():
    state = get_mock_alert_state(AlertTypology.SANCTIONS_MATCH.value)
    # Sanctions match has match_score = 94.5%
    result = risk_router_node(state)

    assert result["risk_tier"] == ReviewTier.TIER_3_FULL
    assert result["audit_log"][-1]["action"] == "RISK_TIER_ASSIGNED"
    assert any("Watchlist" in r for r in result["audit_log"][-1]["details"]["reasons"])


def test_risk_router_tool_failure_routes_to_tier_3():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    # Simulate a tool failure / unavailable database
    state["evidence"]["customer_profile"]["status"] = ToolStatus.UNAVAILABLE.value

    result = risk_router_node(state)

    assert result["risk_tier"] == ReviewTier.TIER_3_FULL
    assert any("customer_profile" in r for r in result["audit_log"][-1]["details"]["reasons"])


def test_risk_router_redraft_history_routes_to_tier_3():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    # Had to be redrafted due to hallucination
    state["redraft_count"] = 1

    result = risk_router_node(state)

    assert result["risk_tier"] == ReviewTier.TIER_3_FULL
    assert any("redraft" in r for r in result["audit_log"][-1]["details"]["reasons"])


def test_risk_router_high_value_routes_to_tier_3():
    state = get_mock_alert_state(AlertTypology.HIGH_VALUE_TRANSFER.value)
    # Volume is $250,000 >= $50,000 threshold
    result = risk_router_node(state)

    assert result["risk_tier"] == ReviewTier.TIER_3_FULL


def test_risk_router_clean_false_positive_routes_to_tier_1():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    # Configure clean, low-risk conditions
    state["verifier_agreed"] = True
    state["redraft_count"] = 0
    state["evidence"]["transactions"]["data"]["total_volume"] = 4500.0
    state["evidence"]["watchlist"]["data"]["highest_similarity_score"] = 5.0
    state["evidence"]["customer_profile"]["data"]["kyc_risk_rating"] = "LOW"

    result = risk_router_node(state)

    assert result["risk_tier"] == ReviewTier.TIER_1_QUICK
    assert result["audit_log"][-1]["action"] == "RISK_TIER_ASSIGNED"


def test_risk_router_moderate_structuring_routes_to_tier_2():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    # Structuring total is $38,100 (between $15,000 and $50,000)
    state["verifier_agreed"] = True
    state["redraft_count"] = 0
    state["evidence"]["watchlist"]["data"]["highest_similarity_score"] = 12.0
    state["evidence"]["customer_profile"]["data"]["kyc_risk_rating"] = "LOW"

    result = risk_router_node(state)

    assert result["risk_tier"] == ReviewTier.TIER_2_STANDARD
