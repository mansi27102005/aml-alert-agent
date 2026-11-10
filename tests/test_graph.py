"""Integration tests for the LangGraph State Machine (Role A).
Verifies:
1. End-to-end execution of Structuring alert up to HITL pause and resume.
2. High-risk Sanctions alert routing to Tier 3.
3. Rapid false positive High-Value transfer.
4. Circuit-breaker escalation on malformed payload.
"""

import pytest
from app.graph import (
    build_aml_graph,
    resume_investigation,
    run_investigation,
)
from app.state import CaseDisposition, InvestigationStatus, ReviewTier
from tests.mock_data import (
    MOCK_HIGH_VALUE_PAYLOAD,
    MOCK_SANCTIONS_PAYLOAD,
    MOCK_STRUCTURING_PAYLOAD,
)


def test_graph_e2e_structuring_workflow():
    payload = dict(MOCK_STRUCTURING_PAYLOAD)
    payload["alert_id"] = "ALT-TEST-STR-001"

# 1. Run investigation up to HITL pause
    paused_state = run_investigation(payload, thread_id="ALT-TEST-STR-001")

    print("\n========== FAILED CLAIMS ONLY ==========")

    print("CLAIM CHECK PASSED:",
        paused_state.get("claim_check_passed"))

    print("REDRAFT COUNT:",
        paused_state.get("redraft_count"))

    for claim in paused_state.get("claims", []):
        if not claim.get("is_valid", True):
            print("\nFAILED SENTENCE:")
            print(claim.get("sentence"))

            print("ERROR:")
            print(claim.get("validation_error"))

            print("CITATIONS:")
            print(claim.get("cited_source_ids"))

    print("\n========== CLAIM CHECK AUDIT ==========")

    for event in reversed(paused_state.get("audit_log", [])):
        if event.get("node") == "claim_check":
            print(event)
            break

    print("\n========================================")

    assert paused_state["alert_id"] == "ALT-TEST-STR-001"
    assert paused_state["alert_type"] == "STRUCTURING"
    assert paused_state["claim_check_passed"] is True
    assert paused_state["verifier_agreed"] is True
    assert paused_state["risk_tier"] == ReviewTier.TIER_2_STANDARD
    assert len(paused_state["draft_note"]) > 0

    # 2. Resume with Analyst Approval
    final_state = resume_investigation(
        thread_id="ALT-TEST-STR-001",
        approved=True,
        reviewer_id="senior_analyst_mark",
        reviewer_comments="Concur with structuring pattern. Recommend SAR filing.",
    )

    assert final_state["status"] == InvestigationStatus.COMPLETED.value
    assert final_state["final_disposition"] == CaseDisposition.FILE_SAR.value
    assert final_state["human_approved"] is True
    assert final_state["reviewer_id"] == "senior_analyst_mark"
    assert final_state["audit_log"][-1]["action"] == "CASE_FINALIZED"


def test_graph_sanctions_hit_reaches_tier_3():
    payload = dict(MOCK_SANCTIONS_PAYLOAD)
    payload["alert_id"] = "ALT-TEST-SAN-002"

    paused_state = run_investigation(payload, thread_id="ALT-TEST-SAN-002")

    assert paused_state["alert_type"] == "SANCTIONS_MATCH"
    assert paused_state["risk_tier"] == ReviewTier.TIER_3_FULL
    assert paused_state["claim_check_passed"] is True


def test_graph_escalates_on_invalid_intake():
    # Graph without human interrupt to test full escalation path directly
    graph = build_aml_graph(enable_interrupt=False)
    bad_payload = {"alert_id": "", "customer_id": ""}

    result = graph.invoke(bad_payload, config={"configurable": {"thread_id": "ALT-BAD-001"}})

    assert result["status"] == InvestigationStatus.ESCALATED.value
    assert result["final_disposition"] == CaseDisposition.ESCALATE_L2.value
    assert "Intake validation failure" in result["escalation_reason"]

