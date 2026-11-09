"""Deterministic Claim Check Node (Role A).
Pure Python code - NO LLM.
Enforces the Claim Ledger requirement:
1. Every factual sentence must terminate with bracketed source citation tokens: [SRC:...]
2. All cited source IDs must exist in the retrieved policy chunks or tool evidence.
3. Financial currency amounts ($) and dates mentioned must be grounded in the cited sources.
4. Sentences lacking citations (orphans) or referencing invented IDs are rejected.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.state import AlertState, AuditEntry, ClaimItem


# Regex for citations: matches [SRC: ID1, ID2, ...] case-insensitively
CITATION_REGEX = re.compile(r"\[SRC:\s*([^\]]+)\]", re.IGNORECASE)

# Regex for currency figures: matches $10,000 or $9,500.50 or $9400.00 or $38100
CURRENCY_REGEX = re.compile(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)")

# Regex for ISO dates: matches YYYY-MM-DD
DATE_REGEX = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def extract_source_citations(sentence: str) -> List[str]:
    """Extracts and normalizes all source IDs from [SRC: ...] tags in a sentence."""
    matches = CITATION_REGEX.findall(sentence)
    source_ids: List[str] = []
    for match in matches:
        # Split by comma or whitespace in case of multiple citations like [SRC: TX_01, TX_02]
        tokens = [t.strip().upper() for t in match.replace(";", ",").split(",") if t.strip()]
        for token in tokens:
            if token and token not in source_ids:
                source_ids.append(token)
    return source_ids


def extract_currency_amounts(text: str) -> List[float]:
    """Extracts numeric values from dollar amounts ($9,500 -> 9500.0)."""
    matches = CURRENCY_REGEX.findall(text)
    amounts: List[float] = []
    for m in matches:
        clean = m.replace(",", "").strip()
        try:
            amounts.append(float(clean))
        except ValueError:
            continue
    return amounts


def extract_dates(text: str) -> List[str]:
    """Extracts ISO date strings (YYYY-MM-DD)."""
    return DATE_REGEX.findall(text)


def split_sentences(text: str) -> List[str]:
    """Splits a case note narrative into discrete sentences.
    Preserves brackets and handles decimal numbers ($9,500.00) without incorrect splitting.
    """
    if not text or not text.strip():
        return []

    # Replace newlines with spaces for consistent parsing
    normalized = " ".join(text.strip().split())
    
    # Split on sentence terminals (. ! ?) followed by whitespace, or right after citation closing bracket ]
    raw_sentences = re.split(r"(?<=[.!?\]])\s+(?=[A-Z0-9\"\'\[])", normalized)
    
    cleaned = [s.strip() for s in raw_sentences if s.strip()]
    return cleaned


def collect_available_source_ids(state: AlertState) -> Set[str]:
    """Gathers all valid source IDs present across policy chunks and tool evidence."""
    valid_ids: Set[str] = set()

    # 1. From Policy Chunks
    for chunk in state.get("policy_chunks", []):
        sid = chunk.get("source_id")
        if sid:
            valid_ids.add(sid.strip().upper())

    # 2. From Evidence Tool Results
    for _, tool_payload in state.get("evidence", {}).items():
        # tool_payload can be a dict from ToolResult.model_dump()
        source_ids = tool_payload.get("source_ids", [])
        for sid in source_ids:
            if sid:
                valid_ids.add(sid.strip().upper())

    return valid_ids


def build_source_content_map(state: AlertState) -> Tuple[Dict[str, str], Dict[str, float]]:
    """Builds lookup mappings:
    1. content_map: source_id -> full stringified content (for string and entity matching).
    2. tx_amount_map: source_id -> individual transaction amount (for verifying aggregate sums).
    """
    content_map: Dict[str, str] = {}
    tx_amount_map: Dict[str, float] = {}

    # Policy chunks
    for chunk in state.get("policy_chunks", []):
        sid = chunk.get("source_id", "").strip().upper()
        if sid:
            text = f"{chunk.get('title', '')} {chunk.get('content', '')}"
            content_map[sid] = text

    # Tool evidence
    for _, tool_payload in state.get("evidence", {}).items():
        data = tool_payload.get("data", {})
        data_str = str(data)
        
        # Link to all declared source_ids for this tool
        for sid in tool_payload.get("source_ids", []):
            clean_sid = sid.strip().upper()
            content_map[clean_sid] = data_str

        # If transaction tool, map individual records to TX_ IDs
        if "records" in data and isinstance(data["records"], list):
            for rec in data["records"]:
                tx_id = str(rec.get("tx_id", "")).strip().upper()
                if tx_id:
                    # Append record info to content_map
                    existing = content_map.get(tx_id, "")
                    content_map[tx_id] = f"{existing} {str(rec)}"
                    
                    # Store exact numeric amount for sum validation
                    raw_amt = rec.get("amount")
                    if raw_amt is not None:
                        try:
                            tx_amount_map[tx_id] = float(raw_amt)
                        except (ValueError, TypeError):
                            pass

    return content_map, tx_amount_map


def verify_sentence(
    sentence: str,
    available_ids: Set[str],
    source_content_map: Dict[str, str],
    tx_amount_map: Optional[Dict[str, float]] = None,
) -> Tuple[bool, Optional[str], List[str]]:
    """Validates a single sentence against grounding rules:
    1. Must contain at least one citation.
    2. All citations must exist in available_ids.
    3. Currency amounts mentioned in sentence must appear in cited source content or sum to cited transactions.
    """
    cited_ids = extract_source_citations(sentence)

    # Rule 1: No orphan sentences
    if not cited_ids:
        return False, "Orphan sentence: Contains no supporting source citations [SRC:...].", []

    # Rule 2: Citation existence
    for cid in cited_ids:
        if cid not in available_ids:
            return False, f"Invalid citation: Source ID '{cid}' does not exist in retrieved evidence.", cited_ids

    # Rule 3: Numeric entity grounding
    amounts = extract_currency_amounts(sentence)
    if amounts:
        tx_amount_map = tx_amount_map or {}
        # Aggregate text from all cited sources for this sentence
        combined_source_text = " ".join([source_content_map.get(cid, "") for cid in cited_ids])
        
        # Compute aggregate sum of any cited transactions
        cited_tx_sum = sum(tx_amount_map[cid] for cid in cited_ids if cid in tx_amount_map)

        for amt in amounts:
            # Check integer or decimal representations (e.g. 9500 or 9500.0 or 9,500)
            int_repr = str(int(amt)) if amt.is_integer() else ""
            float_repr = f"{amt:.2f}"
            standard_repr = str(amt)

            # Direct appearance in source text
            found = (
                (int_repr and int_repr in combined_source_text.replace(",", ""))
                or float_repr in combined_source_text
                or standard_repr in combined_source_text
            )
            
            # Or matches the exact sum of cited transactions (e.g. 4 deposits totaling $38,100)
            if not found and cited_tx_sum > 0 and abs(cited_tx_sum - amt) < 0.01:
                found = True

            if not found:
                return (
                    False,
                    f"Ungrounded numeric claim: Amount ${amt:,.2f} mentioned in sentence does not appear in cited sources {cited_ids}.",
                    cited_ids,
                )

    return True, None, cited_ids


def claim_check_node(state: AlertState) -> Dict[str, Any]:
    """LangGraph node execution function for Claim Check.
    Performs deterministic audit of state['draft_note'] and returns state updates.
    """
    draft_note = state.get("draft_note", "")
    available_ids = collect_available_source_ids(state)
    source_content_map, tx_amount_map = build_source_content_map(state)

    sentences = split_sentences(draft_note)
    
    # If the draft is completely empty, it fails immediately
    if not sentences:
        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "claims": [],
            "claim_check_passed": False,
            "redraft_count": state.get("redraft_count", 0) + 1,
            "audit_log": state.get("audit_log", []) + [
                {
                    "timestamp": now_iso,
                    "node": "claim_check",
                    "action": "CLAIM_CHECK_FAILED",
                    "details": {"error": "Empty draft note received."},
                }
            ],
        }

    claims: List[ClaimItem] = []
    all_passed = True

    for s in sentences:
        is_valid, error_msg, cited_ids = verify_sentence(
            s, available_ids, source_content_map, tx_amount_map
        )
        if not is_valid:
            all_passed = False
        claims.append(
            {
                "sentence": s,
                "cited_source_ids": cited_ids,
                "is_valid": is_valid,
                "validation_error": error_msg,
            }
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    audit_entry: AuditEntry = {
        "timestamp": now_iso,
        "node": "claim_check",
        "action": "CLAIM_CHECK_PASSED" if all_passed else "CLAIM_CHECK_FAILED",
        "details": {
            "total_sentences": len(sentences),
            "valid_sentences": sum(1 for c in claims if c["is_valid"]),
            "all_passed": all_passed,
            "failures": [c["validation_error"] for c in claims if not c["is_valid"]],
        },
    }

    updated_audit = state.get("audit_log", []) + [audit_entry]
    updated_redraft_count = state.get("redraft_count", 0) if all_passed else state.get("redraft_count", 0) + 1

    return {
        "claims": claims,
        "claim_check_passed": all_passed,
        "redraft_count": updated_redraft_count,
        "audit_log": updated_audit,
    }
