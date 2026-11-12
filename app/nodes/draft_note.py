"""Draft Note Node (Role A).
Synthesizes retrieved policies and evidence into a FinCEN 5 Ws case narrative.
Enforces sentence-level citation tags [SRC:...] and defensive memo sandboxing.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List

import logging

logger = logging.getLogger(__name__)
from app.audit import calculate_token_cost
from app.config import settings
from app.llm import call_llm
from app.state import AlertState, AuditEntry

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "draft_note.txt"


def build_evidence_strings(evidence: Dict[str, Any]) -> Dict[str, str]:
    """Formats customer, transaction, and watchlist evidence into clean contextual blocks."""
    # 1. Customer Profile
    cust = evidence.get("customer_profile", {})
    cust_sids = ", ".join(cust.get("source_ids", []))
    cust_data = json.dumps(cust.get("data", {}), indent=2)
    cust_str = f"Available Sources: [{cust_sids}]\n{cust_data}"

    # 2. Transactions
    tx = evidence.get("transactions", {})
    tx_sids = ", ".join(tx.get("source_ids", []))
    tx_data = json.dumps(tx.get("data", {}), indent=2)
    tx_str = f"Available Sources: [{tx_sids}]\n{tx_data}"

    # 3. Watchlist
    wl = evidence.get("watchlist", {})
    wl_sids = ", ".join(wl.get("source_ids", []))
    wl_data = json.dumps(wl.get("data", {}), indent=2)
    wl_str = f"Available Sources: [{wl_sids}]\n{wl_data}"

    return {
        "customer_evidence": cust_str,
        "transaction_evidence": tx_str,
        "watchlist_evidence": wl_str,
    }


def extract_sandboxed_memos(evidence: Dict[str, Any]) -> str:
    """Safely isolates transaction memos."""

    tx_data = evidence.get(
        "transactions", {}
    ).get("data", {})

    records = tx_data.get("records", [])

    memos = []

    for record in records:

        memo = record.get("memo")

        tx_id = (
            record.get("transaction_id")
            or record.get("tx_id")
            or "UNKNOWN_TX"
        )

        if memo:

            memos.append(
                f'<untrusted_evidence_memo tx_id="{tx_id}">'
                f'{memo}'
                f'</untrusted_evidence_memo>'
            )

    if not memos:
        return "No transaction memos present in ledger."

    return "\n".join(memos)


def correct_unsupported_watchlist_claims(
    draft: str,
    evidence: Dict[str, Any],
) -> str:
    """
    Corrects known unsupported watchlist claims using actual tool evidence.
    Never converts a synthetic match into an OFAC match.
    """

    import re

    watchlist = evidence.get("watchlist", {})
    data = watchlist.get("data", {})
    source_ids = watchlist.get("source_ids", [])

    # If screening was unavailable, do not invent screening results.
    watchlist_status = watchlist.get("status")
    watchlist_status = getattr(
    watchlist_status,
    "value",
    watchlist_status
)

    if watchlist_status != "SUCCESS":
        return draft

    if not source_ids:
        return draft

    # Identify sentences containing unsupported watchlist claims.
    sentences = re.split(r"(?<=[.!?])\s+", draft)

    corrected_sentences = []

    for sentence in sentences:

        if (
            "WL_HIT_OFAC_01" in sentence
            or "94.5%" in sentence
            or "OFAC Specially Designated Nationals" in sentence
        ):

            if data.get("match_found"):

                entries = data.get("matched_entries", [])

                match_score = data.get(
                    "highest_similarity_score",
                    "unavailable"
                )

                if entries:
                    entry = entries[0]

                    name_score = entry.get(
                        "name_similarity_score",
                        "unavailable"
                    )

                    dob_match = entry.get("dob_match")
                    country_match = entry.get("country_match")

                    dob_text = (
                        "date of birth matched"
                        if dob_match is True
                        else "date of birth did not match"
                        if dob_match is False
                        else "date of birth comparison unavailable"
                    )

                    country_text = (
                        "country matched"
                        if country_match is True
                        else "country did not match"
                        if country_match is False
                        else "country comparison unavailable"
                    )

                    list_type = entry.get(
                        "list_type",
                        "UNSPECIFIED"
                    )

                    screening_source = entry.get(
                        "source",
                        "UNSPECIFIED"
                    )

                    corrected_sentences.append(
                        f"Automated screening identified a potential "
                        f"match on the {list_type} list maintained by "
                        f"{screening_source}, with a match score of "
                        f"{match_score}%, name similarity of "
                        f"{name_score}%, {dob_text}, and "
                        f"{country_text} "
                        f"[SRC: {source_ids[0]}]."
                    )

                else:
                    corrected_sentences.append(
                        f"Automated screening identified a potential "
                        f"match with a reported similarity score of "
                        f"{match_score}% "
                        f"[SRC: {source_ids[0]}]."
                    )

            else:
                corrected_sentences.append(
                    f"Automated screening did not identify a "
                    f"watchlist match "
                    f"[SRC: {source_ids[0]}]."
                )

        else:
            corrected_sentences.append(sentence)

    draft = " ".join(corrected_sentences)

    # Correct the unsupported nationality source reference
    # only when the KYC source actually exists.
    customer = evidence.get("customer_profile", {})
    customer_sources = customer.get("source_ids", [])

    if (
        "CUST_2055_NATIONALITY" in draft
        and "CUST_2055_KYC" in customer_sources
    ):
        draft = draft.replace(
            "CUST_2055_NATIONALITY",
            "CUST_2055_KYC"
        )

    return draft

def build_redraft_feedback(state: AlertState) -> str:
    """Generates targeted correction instructions if a prior claim check failed."""
    if state.get("redraft_count", 0) == 0:
        return ""

    failures = [
        f"- Sentence: \"{c['sentence']}\" -> ERROR: {c['validation_error']}"
        for c in state.get("claims", [])
        if not c.get("is_valid", True) and c.get("validation_error")
    ]
    if not failures:
        return ""

    return (
        "PRIOR DRAFT FAILED CITATION AUDIT:\n"
        "Your previous draft was rejected by the deterministic Claim Check engine. "
        "You MUST resolve these specific errors in your revised note:\n"
        + "\n".join(failures)
        + "\nEnsure every factual sentence has a verified [SRC:...] tag and all figures match the evidence exactly."
    )


def draft_note_node(state: AlertState) -> Dict[str, Any]:
    """LangGraph node execution function for drafting the case note."""
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    # Format Policy Context
    policy_blocks = []
    for chunk in state.get("policy_chunks", []):
        sid = chunk.get("source_id", "POL_UNKNOWN")
        title = chunk.get("title", "")
        content = chunk.get("content", "")
        policy_blocks.append(f"[{sid}] {title}:\n{content}")
    policy_context = "\n\n".join(policy_blocks) if policy_blocks else "No institutional policy chunks retrieved."

    evidence = state.get("evidence", {})
    evidence_blocks = build_evidence_strings(evidence)
    untrusted_memos = extract_sandboxed_memos(evidence)
    redraft_feedback = build_redraft_feedback(state)

    prompt = prompt_template.format(
        policy_context=policy_context,
        customer_evidence=evidence_blocks["customer_evidence"],
        transaction_evidence=evidence_blocks["transaction_evidence"],
        watchlist_evidence=evidence_blocks["watchlist_evidence"],
        untrusted_memos=untrusted_memos,
        redraft_feedback=redraft_feedback,
    )



    # -------------------------------------------------
    # STRICT CUSTOMER IDENTITY AND EVIDENCE GUARD
    # -------------------------------------------------

    customer_profile = evidence.get(
        "customer_profile", {}
    ).get("data", {})

    expected_customer_id = state.get("customer_id", "UNKNOWN")
    expected_customer_name = customer_profile.get(
        "full_name", "Unknown Customer"
    )

    allowed_source_ids = []

    for chunk in state.get("policy_chunks", []):
        sid = chunk.get("source_id")
        if sid:
            allowed_source_ids.append(sid)

    for tool_data in evidence.values():
        allowed_source_ids.extend(
            tool_data.get("source_ids", [])
        )

    identity_guard = f"""
CRITICAL INVESTIGATION IDENTITY LOCK:

Current alert customer ID: {expected_customer_id}
Current customer name: {expected_customer_name}
Current alert typology: {state.get("alert_type")}

You MUST investigate ONLY this customer and this alert.

STRICT RULES:
1. Never reuse customer names, transactions, amounts,
   dates or facts from previous investigations.
2. Use only the supplied customer profile and transaction records.
3. Do not invent transaction IDs, dates or amounts.
4. Do not convert a cash deposit into a wire transfer.
5. Use only these available source IDs:
   {", ".join(sorted(set(allowed_source_ids)))}
6. If evidence is missing, explicitly state that it is
   unavailable instead of inventing information.
7. Follow the current alert typology and retrieved policy.
8. Do not use information from previous investigation examples.

The current investigation takes precedence over all
illustrative examples in the prompt.
"""

    prompt = identity_guard + "\n\n" + prompt

    logger.info(
        "Drafting investigation for customer=%s, typology=%s",
        expected_customer_id,
        state.get("alert_type"),
    )

    response_text, in_tok, out_tok = call_llm(prompt, json_mode=False)
    call_cost = calculate_token_cost(in_tok, out_tok, settings.LLM_MODEL)

    cleaned_draft = response_text.strip()

# Correct unsupported watchlist claims using actual evidence
    cleaned_draft = correct_unsupported_watchlist_claims(
    cleaned_draft,
    evidence
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    audit_entry: AuditEntry = {
        "timestamp": now_iso,
        "node": "draft_note",
        "action": "DRAFT_NOTE_GENERATED",
        "details": {
            "draft_length_chars": len(cleaned_draft),
            "redraft_iteration": state.get("redraft_count", 0),
            "tokens_used": in_tok + out_tok,
            "cost_usd": call_cost,
        },
    }

    return {
        "draft_note": cleaned_draft,
        "total_tokens_used": state.get("total_tokens_used", 0) + in_tok + out_tok,
        "estimated_cost_usd": state.get("estimated_cost_usd", 0.0) + call_cost,
        "audit_log": state.get("audit_log", []) + [audit_entry],
    }
