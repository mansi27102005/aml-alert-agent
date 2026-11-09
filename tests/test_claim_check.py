"""Unit tests for the Deterministic Claim Check Node (Role A).
Verifies:
1. 100% pass on legitimate citations and grounded facts.
2. Rejection of orphan sentences (no citation tags).
3. Rejection of hallucinated source IDs.
4. Rejection of fabricated currency amounts ($).
5. Proper audit logging and redraft counter incrementation.
"""

import pytest
from app.nodes.claim_check import (
    claim_check_node,
    extract_currency_amounts,
    extract_source_citations,
    split_sentences,
)
from app.state import AlertTypology
from tests.mock_data import (
    MOCK_STRUCTURING_EVIDENCE,
    MOCK_STRUCTURING_POLICY_CHUNKS,
    VALID_STRUCTURING_DRAFT,
    get_mock_alert_state,
)


def test_split_sentences_basic():
    text = "First sentence [SRC:TX_01]. Second sentence [SRC:TX_02]! Third sentence?"
    sentences = split_sentences(text)
    assert len(sentences) == 3
    assert sentences[0] == "First sentence [SRC:TX_01]."
    assert sentences[1] == "Second sentence [SRC:TX_02]!"
    assert sentences[2] == "Third sentence?"


def test_split_sentences_preserves_decimals_and_commas():
    text = "Customer transferred $9,500.50 on 2026-10-12 [SRC:TX_01]. A second transfer followed [SRC:TX_02]."
    sentences = split_sentences(text)
    assert len(sentences) == 2
    assert "$9,500.50" in sentences[0]


def test_extract_source_citations():
    s = "Alex Rivera is a Cashier [SRC: CUST_1049_KYC, CUST_1049_OCCUPATION]."
    cids = extract_source_citations(s)
    assert cids == ["CUST_1049_KYC", "CUST_1049_OCCUPATION"]


def test_extract_currency_amounts():
    s = "Deposited $9,500, then $9400.00 and finally $10,000."
    amounts = extract_currency_amounts(s)
    assert amounts == [9500.0, 9400.0, 10000.0]


def test_claim_check_valid_draft():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    state["draft_note"] = VALID_STRUCTURING_DRAFT

    result = claim_check_node(state)

    assert result["claim_check_passed"] is True
    assert len(result["claims"]) > 0
    assert all(c["is_valid"] for c in result["claims"])
    assert result["redraft_count"] == 0
    assert result["audit_log"][-1]["action"] == "CLAIM_CHECK_PASSED"


def test_claim_check_rejects_orphan_sentence():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    # Missing source tag on the second sentence
    state["draft_note"] = (
        "Customer Alex Rivera is employed as a Retail Cashier [SRC:CUST_1049_KYC]. "
        "The customer recently bought a luxury sports car with cash. "
        "No sanctions match found [SRC:WL_CLEAN_1049]."
    )

    result = claim_check_node(state)

    assert result["claim_check_passed"] is False
    assert result["redraft_count"] == 1
    # Check that sentence 2 is marked invalid as orphan
    orphan_claim = result["claims"][1]
    assert orphan_claim["is_valid"] is False
    assert "Orphan sentence" in orphan_claim["validation_error"]
    assert result["audit_log"][-1]["action"] == "CLAIM_CHECK_FAILED"


def test_claim_check_rejects_hallucinated_source_id():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    state["draft_note"] = (
        "Customer Alex Rivera is employed as a Retail Cashier [SRC:CUST_1049_KYC]. "
        "Customer has 10 undisclosed foreign accounts [SRC:TX_FABRICATED_9999]."
    )

    result = claim_check_node(state)

    assert result["claim_check_passed"] is False
    assert result["redraft_count"] == 1
    bad_claim = result["claims"][1]
    assert bad_claim["is_valid"] is False
    assert "TX_FABRICATED_9999" in bad_claim["validation_error"]


def test_claim_check_rejects_ungrounded_currency_figure():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    # The actual transaction TX_8801 is $9,500, but LLM claims $950,000
    state["draft_note"] = (
        "Customer Alex Rivera deposited $950,000 on 2026-10-12 [SRC:TX_8801]."
    )

    result = claim_check_node(state)

    assert result["claim_check_passed"] is False
    bad_claim = result["claims"][0]
    assert bad_claim["is_valid"] is False
    assert "Ungrounded numeric claim" in bad_claim["validation_error"]
    assert "$950,000.00" in bad_claim["validation_error"]


def test_claim_check_empty_draft():
    state = get_mock_alert_state(AlertTypology.STRUCTURING.value)
    state["draft_note"] = ""

    result = claim_check_node(state)

    assert result["claim_check_passed"] is False
    assert result["redraft_count"] == 1
    assert result["audit_log"][-1]["action"] == "CLAIM_CHECK_FAILED"
