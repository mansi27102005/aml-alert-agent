"""Draft Note Node (Role A).
Synthesizes retrieved policies and evidence into a FinCEN 5 Ws case narrative.
Enforces sentence-level citation tags [SRC:...] and defensive memo sandboxing.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List
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
    """Isolates transaction memos inside strict XML boundaries to mitigate prompt injection."""
    tx_data = evidence.get("transactions", {}).get("data", {})
    records = tx_data.get("records", [])

    memos: List[str] = []
    for r in records:
        memo = r.get("memo")
        tx_id = r.get("tx_id", "UNKNOWN_TX")
        if memo:
            memos.append(f'<untrusted_evidence_memo tx_id="{tx_id}">{memo}</untrusted_evidence_memo>')

    if not memos:
        return "No transaction memos present in ledger."
    return "\n".join(memos)


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

    response_text, in_tok, out_tok = call_llm(prompt, json_mode=False)
    call_cost = calculate_token_cost(in_tok, out_tok, settings.LLM_MODEL)

    cleaned_draft = response_text.strip()

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
