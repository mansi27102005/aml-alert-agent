"""Unit tests for LangGraph node handlers (Role A).
Verifies:
1. Intake validation
2. Typology classification
3. Case note drafting with FinCEN narrative and citations
4. Adversarial verifier review
5. Human decision application
6. Escalation circuit-breaker
7. Case finalization
"""

import pytest
from app.nodes.classify import classify_node
from app.nodes.draft_note import draft_note_node
from app.nodes.escalate import escalate_node
from app.nodes.finalize import finalize_node
from app.nodes.gather_evidence import gather_evidence_node
from app.nodes.human_approval import apply_human_decision, human_approval_node
from app.nodes.intake import intake_node
from app.nodes.retrieve_policy import retrieve_policy_node
from app.nodes.verifier import verifier_node
from app.state import AlertTypology, CaseDisposition, InvestigationStatus
from tests.mock_data import get_mock_alert_state


def test_intake_node_valid():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    result = intake_node(state)
    assert result["status"] == InvestigationStatus.IN_PROGRESS.value
    assert result["audit_log"][-1]["action"] == "INTAKE_VALIDATED"


def test_intake_node_missing_id():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    state["alert_id"] = ""
    result = intake_node(state)
    assert result["status"] == InvestigationStatus.ESCALATED.value
    assert "Intake validation failure" in result["escalation_reason"]


def test_classify_node():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    state["alert_type"] = None  # Force classifier to run
    result = classify_node(state)
    assert result["alert_type"] in [
        AlertTypology.STRUCTURING.value,
        AlertTypology.SANCTIONS_MATCH.value,
        AlertTypology.HIGH_VALUE_TRANSFER.value,
    ]
    assert result["total_tokens_used"] > 0
    assert result["audit_log"][-1]["action"] == "ALERT_CLASSIFIED"


def test_retrieve_policy_node():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    state["policy_chunks"] = []
    result = retrieve_policy_node(state)
    assert len(result["policy_chunks"]) > 0
    assert "POL_STRUCT_01" in [c["source_id"] for c in result["policy_chunks"]]


def test_gather_evidence_node():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    state["evidence"] = {}
    result = gather_evidence_node(state)
    assert "customer_profile" in result["evidence"]
    assert "transactions" in result["evidence"]
    assert "watchlist" in result["evidence"]


def test_draft_note_node():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    result = draft_note_node(state)
    assert len(result["draft_note"]) > 0
    assert "[SRC:" in result["draft_note"]
    assert result["total_tokens_used"] > 0


def test_verifier_node():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    state["draft_note"] = "Customer Alex Rivera deposited sub-threshold amounts [SRC:TX_8801]."
    result = verifier_node(state)
    assert isinstance(result["verifier_agreed"], bool)
    assert len(result["verifier_notes"]) > 0
    assert result["audit_log"][-1]["action"] == "VERIFICATION_AUDIT_COMPLETED"


def test_human_approval_node():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    result = human_approval_node(state)
    assert result["status"] == InvestigationStatus.AWAITING_APPROVAL.value


def test_apply_human_decision():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    updates = apply_human_decision(
        state,
        approved=True,
        reviewer_id="analyst_jane",
        edited_note="Edited note content",
        reviewer_comments="Looks good",
    )
    assert updates["human_approved"] is True
    assert updates["reviewer_id"] == "analyst_jane"
    assert updates["human_edits"] == "Edited note content"


def test_escalate_node():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    state["redraft_count"] = 2
    state["claim_check_passed"] = False
    result = escalate_node(state)
    assert result["status"] == InvestigationStatus.ESCALATED.value
    assert result["final_disposition"] == CaseDisposition.ESCALATE_L2.value
    assert "redraft" in result["escalation_reason"].lower()


def test_finalize_node_completed():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    state["human_approved"] = True
    state["draft_note"] = "Recommendation: File Suspicious Activity Report (SAR) [SRC:POL_STRUCT_01]."
    result = finalize_node(state)
    assert result["status"] == InvestigationStatus.COMPLETED.value
    assert result["final_disposition"] == CaseDisposition.FILE_SAR.value
    assert result["audit_log"][-1]["action"] == "CASE_FINALIZED"

