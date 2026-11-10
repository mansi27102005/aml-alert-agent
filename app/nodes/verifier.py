
"""Verifier Node (Role A).
Independent second-line compliance QA.

Performs:
1. Claim Check prerequisite validation.
2. Adversarial LLM verification.
3. High-confidence sanctions-match safeguards.
4. Strict JSON response validation.
5. Fail-closed escalation on verification errors.
6. Audit logging and token-cost tracking.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict

from app.audit import calculate_token_cost
from app.config import settings
from app.llm import call_llm
from app.state import AlertState, AuditEntry

logger = logging.getLogger(__name__)

PROMPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "prompts"
    / "verifier.txt"
)


def has_high_confidence_match(evidence: Dict[str, Any]) -> bool:
    """
    Detect a screening match with similarity >= 80%.

    This detects potential or synthetic internal-list matches too.
    It does NOT establish a confirmed OFAC match.
    """

    watchlist = evidence.get("watchlist", {})
    data = watchlist.get("data", {})

    if not data.get("match_found", False):
        return False

    highest_score = data.get(
        "highest_similarity_score",
        data.get("match_score", 0)
    )

    try:
        return float(highest_score) >= 80.0
    except (ValueError, TypeError):
        return False


def draft_recommends_false_positive_closure(draft: str) -> bool:
    """Detect an explicit false-positive closure recommendation."""

    text = draft.lower()

    closure_phrases = [
        "close_false_positive",
        "close alert as false positive",
        "close the alert",
        "recommendation: close alert",
        "recommendation: close_false_positive",
    ]

    return any(phrase in text for phrase in closure_phrases)


def build_verifier_context(state: AlertState) -> tuple:
    """Build policy and evidence context for independent review."""

    policies = state.get("policy_chunks", [])

    policy_summary = "\n".join(
        [
            f"[{p.get('source_id')}]: {p.get('content', '')}"
            for p in policies
        ]
    ) or "No policies provided."

    evidence = state.get("evidence", {})

    evidence_summary = json.dumps(
        {
            tool: data.get("data", {})
            for tool, data in evidence.items()
        },
        indent=2,
        default=str,
    )

    return policy_summary, evidence_summary


def verifier_node(state: AlertState) -> Dict[str, Any]:
    """LangGraph execution function for independent compliance QA."""

    now_iso = datetime.now(timezone.utc).isoformat()

    # -------------------------------------------------
    # SAFEGUARD 1: CLAIM CHECK MUST PASS
    # -------------------------------------------------

    if not state.get("claim_check_passed", False):

        critique = (
            "Verification blocked because deterministic Claim Check "
            "did not pass. The investigation requires escalation."
        )

        audit_entry: AuditEntry = {
            "timestamp": now_iso,
            "node": "verifier",
            "action": "VERIFICATION_BLOCKED",
            "details": {
                "reason": "CLAIM_CHECK_FAILED",
                "verifier_agreed": False,
            },
        }

        return {
            "verifier_agreed": False,
            "verifier_notes": critique,
            "audit_log": (
                state.get("audit_log", []) + [audit_entry]
            ),
        }

    # -------------------------------------------------
    # BUILD VERIFICATION PROMPT
    # -------------------------------------------------

    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    policy_summary, evidence_summary = (
        build_verifier_context(state)
    )

    draft_note = state.get("draft_note", "")

    prompt = (
    prompt_template
    .replace("{policy_context}", policy_summary)
    .replace("{evidence_summary}", evidence_summary)
    .replace("{draft_note}", draft_note)
)

    # -------------------------------------------------
    # INDEPENDENT LLM VERIFICATION
    # -------------------------------------------------

    agreed = False
    critique = ""
    flaws = []
    action = "ESCALATE_TO_SENIOR"

    in_tok = 0
    out_tok = 0
    call_cost = 0.0
    verification_completed = False

    try:

        response_text, in_tok, out_tok = call_llm(
            prompt,
            json_mode=True,
        )

        call_cost = calculate_token_cost(
            in_tok,
            out_tok,
            settings.LLM_MODEL,
        )

        data = json.loads(response_text)

        # Strict response schema validation
        if not isinstance(data, dict):
            raise ValueError("Verifier response must be a JSON object.")

        if not isinstance(data.get("agreed"), bool):
            raise ValueError("Verifier must return a boolean 'agreed' field.")

        agreed = data["agreed"]

        critique = str(
            data.get("skeptic_critique", "")
        )

        flaws = data.get("flaws_found", [])

        if not isinstance(flaws, list):
            raise ValueError("'flaws_found' must be a list.")

        action = str(
            data.get(
                "recommended_action",
                "ESCALATE_TO_SENIOR"
            )
        )
        verification_completed = True

    except Exception as exc:

        logger.exception("Verifier execution failed: %s", exc)

        agreed = False
        critique = (
            "Independent verification failed. "
            f"Reason: {str(exc)}"
        )

        flaws = [
            "Verifier response could not be reliably validated."
        ]

        action = "ESCALATE_TO_SENIOR"

    # -------------------------------------------------
    # SAFEGUARD 2: HIGH-CONFIDENCE SCREENING MATCH
    # -------------------------------------------------

    evidence = state.get("evidence", {})

    if (
        has_high_confidence_match(evidence)
        and draft_recommends_false_positive_closure(draft_note)
    ):

        agreed = False

        critique += (
            " Deterministic safeguard: The screening evidence "
            "contains a match score of at least 80%, while the "
            "draft recommends false-positive closure. "
            "Human sanctions review is required."
        )

        flaws.append(
            "Potential high-confidence screening match cannot "
            "be automatically closed as a false positive."
        )

        action = "ESCALATE_TO_SENIOR"

    # -------------------------------------------------
    # SAFEGUARD 3: FLAWS MUST NOT BE IGNORED
    # -------------------------------------------------

    if flaws:
        agreed = False
        action = "ESCALATE_TO_SENIOR"

    # -------------------------------------------------
    # AUDIT LOG
    # -------------------------------------------------

    audit_entry: AuditEntry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": "verifier",
        "action": (
    "VERIFICATION_AUDIT_COMPLETED"
    if verification_completed
    else "VERIFICATION_AUDIT_FAILED"
),
        "details": {
            "verifier_agreed": agreed,
            "recommended_action": action,
            "flaws_detected_count": len(flaws),
            "flaws_found": flaws,
            "skeptic_critique": critique,
            "tokens_used": in_tok + out_tok,
            "cost_usd": call_cost,
        },
    }

    return {
        "verifier_agreed": agreed,
        "verifier_notes": critique,
        "total_tokens_used": (
            state.get("total_tokens_used", 0)
            + in_tok
            + out_tok
        ),
        "estimated_cost_usd": (
            state.get("estimated_cost_usd", 0.0)
            + call_cost
        ),
        "audit_log": (
            state.get("audit_log", [])
            + [audit_entry]
        ),
    }
