"""Deterministic Risk Router Node (Role A).
Pure Python code - NO LLM.
Calculates the operational Human-in-the-Loop review tier:
- TIER_1_QUICK: 1-click closure for low-risk, verified false positives.
- TIER_2_STANDARD: Standard analyst review with side-by-side evidence inspection.
- TIER_3_FULL: Senior compliance officer review for sanctions hits, tool failures, or high-value structuring.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from app.state import AlertState, AuditEntry, ReviewTier, ToolStatus


def evaluate_risk_tier(state: AlertState) -> Tuple[ReviewTier, List[str]]:
    """Evaluates deterministic risk rules and returns (ReviewTier, list_of_reasons)."""
    tier_3_reasons: List[str] = []
    tier_1_disqualifiers: List[str] = []

    evidence = state.get("evidence", {})
    alert_type = state.get("alert_type", "")
    redraft_count = state.get("redraft_count", 0)
    verifier_agreed = state.get("verifier_agreed", False)

    # 1. Tool Failures / Missing Evidence -> Automatic Tier 3
    for tool_name, tool_data in evidence.items():
        status = tool_data.get("status")
        if status != ToolStatus.SUCCESS.value:
            tier_3_reasons.append(f"Tool '{tool_name}' status is {status} (missing evidence)")

    # 2. Watchlist Match Score Check
    wl_data = evidence.get("watchlist", {}).get("data", {})
    match_score = float(wl_data.get("highest_similarity_score", 0.0))
    match_found = bool(wl_data.get("match_found", False))

    if match_score >= 80.0 or match_found:
        tier_3_reasons.append(f"Watchlist match flagged (score: {match_score:.1f}%)")
    elif match_score >= 60.0:
        tier_1_disqualifiers.append(f"Moderate watchlist similarity score ({match_score:.1f}%)")

    # 3. Transaction Volume & Structuring Amounts
    tx_data = evidence.get("transactions", {}).get("data", {})
    total_volume = float(tx_data.get("total_volume", 0.0))
    if total_volume == 0.0 and "records" in tx_data:
        total_volume = sum(float(r.get("amount", 0.0)) for r in tx_data.get("records", []))

    if total_volume >= 50000.0:
        tier_3_reasons.append(f"High transaction volume (${total_volume:,.2f} >= $50,000)")
    elif total_volume >= 15000.0:
        tier_1_disqualifiers.append(f"Transaction volume (${total_volume:,.2f} >= $15,000)")

    # 4. KYC Risk Rating
    cust_data = evidence.get("customer_profile", {}).get("data", {})
    kyc_rating = str(cust_data.get("kyc_risk_rating", "")).upper()
    if kyc_rating == "HIGH":
        tier_3_reasons.append("Customer KYC risk rating is HIGH")
    elif kyc_rating != "LOW":
        tier_1_disqualifiers.append(f"Customer KYC risk rating is {kyc_rating or 'UNKNOWN'}")

    # 5. Hallucination / Redraft History
    if redraft_count > 0:
        tier_3_reasons.append(f"Required {redraft_count} redraft(s) to pass claim check")

    # 6. Verifier Disagreement
    if not verifier_agreed:
        tier_1_disqualifiers.append("Verifier did not confirm unanimous agreement")

    # Final Decision Resolution
    if tier_3_reasons:
        return ReviewTier.TIER_3_FULL, tier_3_reasons

    # Check eligibility for Tier 1 (Quick Review)
    if not tier_1_disqualifiers:
        reasons = [
            "All tools successful",
            f"Low transaction volume (${total_volume:,.2f})",
            "Clean watchlist (<60% similarity)",
            "Zero redrafts required",
            "Verifier agreed",
        ]
        return ReviewTier.TIER_1_QUICK, reasons

    # Otherwise default to Tier 2 (Standard Review)
    return ReviewTier.TIER_2_STANDARD, tier_1_disqualifiers


def risk_router_node(state: AlertState) -> Dict[str, Any]:
    """LangGraph node execution function for Risk Router.
    Assigns state['risk_tier'] and appends an immutable audit entry.
    """
    assigned_tier, reasons = evaluate_risk_tier(state)

    now_iso = datetime.now(timezone.utc).isoformat()
    audit_entry: AuditEntry = {
        "timestamp": now_iso,
        "node": "risk_router",
        "action": "RISK_TIER_ASSIGNED",
        "details": {
            "risk_tier": assigned_tier.value,
            "reasons": reasons,
        },
    }

    updated_audit = state.get("audit_log", []) + [audit_entry]

    return {
        "risk_tier": assigned_tier,
        "audit_log": updated_audit,
    }
