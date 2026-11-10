
"""
Deterministic Claim Check Node (Role A).
Pure Python validation - NO LLM.

Validates:
1. Every factual sentence has source citations.
2. Every cited source ID exists in retrieved evidence.
3. Currency amounts are grounded in cited evidence.
4. Dates are grounded in cited evidence.
5. Aggregate transaction amounts match cited transaction records.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.state import AlertState, AuditEntry, ClaimItem


# =========================================================
# REGEX
# =========================================================

CITATION_REGEX = re.compile(
    r"\[SRC:\s*([^\]]+)\]",
    re.IGNORECASE
)

CURRENCY_REGEX = re.compile(
    r"\$\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.\d+)?|[0-9]+(?:\.\d+)?)"
)

DATE_REGEX = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


# =========================================================
# SOURCE NORMALIZATION
# =========================================================


def normalize_source_id(source_id: str) -> str:
    """
    Normalize source IDs while preserving underscores.

    TX_20011 and TX-20011 both become TX_20011.
    CUST_1049_KYC remains CUST_1049_KYC.
    """
    value = str(source_id).strip().upper()
    value = value.replace("-", "_")
    return re.sub(r"[^A-Z0-9_]", "", value)



def extract_source_citations(sentence: str) -> List[str]:

    matches = CITATION_REGEX.findall(sentence)

    source_ids = []

    for match in matches:

        tokens = re.split(r"[,;]+", match)

        for token in tokens:

            token = normalize_source_id(token.strip())

            if token and token not in source_ids:
                source_ids.append(token)

    return source_ids


def extract_currency_amounts(text: str) -> List[Decimal]:

    amounts = []

    for match in CURRENCY_REGEX.findall(text):

        try:
            amounts.append(
                Decimal(match.replace(",", ""))
            )
        except InvalidOperation:
            pass

    return amounts


def extract_dates(text: str) -> List[str]:
    return DATE_REGEX.findall(text)


# =========================================================
# SENTENCE SPLITTING
# =========================================================

def split_sentences(text: str) -> List[str]:
    """
    Split narrative into sentences while KEEPING [SRC:...] citations
    attached to their corresponding factual sentences.
    """

    if not text or not text.strip():
        return []

    normalized = " ".join(text.strip().split())

    normalized = re.sub(
        r"^DRAFT CASE NARRATIVE\s*:\s*",
        "",
        normalized,
        flags=re.IGNORECASE
    )

    # IMPORTANT:
    # Do not include '[' in the lookahead.
    # Otherwise [SRC:...] gets separated from its sentence.
    raw_sentences = re.split(
        r"(?<=[.!?])\s+(?=[A-Z0-9])",
        normalized
    )

    return [
        sentence.strip()
        for sentence in raw_sentences
        if sentence.strip()
    ]


# =========================================================
# AVAILABLE SOURCE IDS
# =========================================================

def collect_available_source_ids(
    state: AlertState
) -> Set[str]:

    valid_ids = set()

    # Retrieved policy sources
    for chunk in state.get("policy_chunks", []):

        sid = chunk.get("source_id")

        if sid:
            valid_ids.add(
                normalize_source_id(sid)
            )

    # Banking evidence sources
    for tool_payload in state.get("evidence", {}).values():

        for sid in tool_payload.get("source_ids", []):

            if sid:
                valid_ids.add(
                    normalize_source_id(sid)
                )

    return valid_ids


# =========================================================
# SOURCE CONTENT AND TRANSACTION MAPPING
# =========================================================

def build_source_content_map(
    state: AlertState
) -> Tuple[Dict[str, str], Dict[str, Decimal]]:
    """
    Maps:
    1. Normalized source IDs to evidence content.
    2. Normalized transaction IDs to exact transaction amounts.

    Handles:
    TX_20011 == TX-20011 == TX20011
    """

    content_map: Dict[str, str] = {}

    tx_amount_map: Dict[str, Decimal] = {}

    # -----------------------------------------------------
    # POLICY CONTENT
    # -----------------------------------------------------

    for chunk in state.get("policy_chunks", []):

        sid = normalize_source_id(
            chunk.get("source_id", "")
        )

        if sid:

            content_map[sid] = (
                str(chunk.get("title", ""))
                + " "
                + str(chunk.get("content", ""))
            )

    # -----------------------------------------------------
    # TOOL EVIDENCE
    # -----------------------------------------------------

    for tool_payload in state.get("evidence", {}).values():

        data = tool_payload.get("data", {})

        data_str = str(data)

        # Map tool evidence to its source IDs
        for sid in tool_payload.get("source_ids", []):

            clean_sid = normalize_source_id(sid)

            if clean_sid:

                content_map[clean_sid] = data_str

        # Extract individual transaction records
        records = data.get("records", [])

        if isinstance(records, list):

            for record in records:

                raw_tx_id = (
                    record.get("transaction_id")
                    or record.get("tx_id")
                    or ""
                )

                tx_id = normalize_source_id(raw_tx_id)

                if not tx_id:
                    continue

                content_map[tx_id] = (
                    content_map.get(tx_id, "")
                    + " "
                    + str(record)
                )

                raw_amount = record.get("amount")

                if raw_amount is not None:

                    try:
                        tx_amount_map[tx_id] = Decimal(
                            str(raw_amount)
                        )

                    except (
                        InvalidOperation,
                        ValueError,
                        TypeError
                    ):
                        pass

    return content_map, tx_amount_map


# =========================================================
# NUMERIC VALIDATION
# =========================================================


def verify_currency_amount(
    amount: Decimal,
    cited_ids: List[str],
    source_content_map: Dict[str, str],
    tx_amount_map: Dict[str, Decimal],
) -> bool:
    """
    Verify currency amounts against cited evidence.

    Supports:
    1. Amounts written with $ signs.
    2. Amounts written without $ signs in policy documents.
    3. Exact individual transaction amounts.
    4. Aggregate transaction amounts.
    """

    combined_text = " ".join(
        source_content_map.get(sid, "")
        for sid in cited_ids
    )

    # Extract numeric amounts from cited evidence.
    # This also recognizes policy thresholds such as 10,000
    # when the policy does not explicitly include a $ sign.
    number_pattern = re.compile(
        r"(?<![A-Za-z0-9_])"
        r"(?:USD\s*)?\$?\s*"
        r"([0-9]{1,3}(?:,[0-9]{3})+(?:\.\d+)?|"
        r"[0-9]+(?:\.\d+)?)"
        r"(?![A-Za-z0-9_])",
        re.IGNORECASE
    )

    source_amounts = []

    for match in number_pattern.findall(combined_text):
        try:
            source_amounts.append(
                Decimal(match.replace(",", ""))
            )
        except InvalidOperation:
            continue

    # Direct evidence match
    if amount in source_amounts:
        return True

    # Transaction-level evidence
    cited_transaction_amounts = [
        tx_amount_map[sid]
        for sid in cited_ids
        if sid in tx_amount_map
    ]

    if cited_transaction_amounts:

        # Individual transaction match
        if amount in cited_transaction_amounts:
            return True

        # Aggregate transaction match
        cited_sum = sum(
            cited_transaction_amounts,
            Decimal("0")
        )

        if cited_sum == amount:
            return True

    return False



# =========================================================
# SENTENCE VALIDATION
# =========================================================

def verify_sentence(
    sentence: str,
    available_ids: Set[str],
    source_content_map: Dict[str, str],
    tx_amount_map: Optional[Dict[str, Decimal]] = None,
) -> Tuple[bool, Optional[str], List[str]]:

    cited_ids = extract_source_citations(sentence)

    tx_amount_map = tx_amount_map or {}

    # Normalize IDs
    available = {
        normalize_source_id(sid)
        for sid in available_ids
    }

    cited_ids = [
        normalize_source_id(sid)
        for sid in cited_ids
    ]

    # -----------------------------------------------------
    # RULE 1: CITATION REQUIRED
    # -----------------------------------------------------

    if not cited_ids:

        return (
            False,
            "Orphan sentence: Contains no supporting source citations [SRC:...].",
            []
        )

    # -----------------------------------------------------
    # RULE 2: CITATION MUST EXIST
    # -----------------------------------------------------

    for cid in cited_ids:

        if cid not in available:

            return (
                False,
                f"Invalid citation: Source ID '{cid}' does not exist in retrieved evidence.",
                cited_ids
            )

    # -----------------------------------------------------
    # RULE 3: CURRENCY GROUNDING
    # -----------------------------------------------------

    for amount in extract_currency_amounts(sentence):

        grounded = verify_currency_amount(
            amount,
            cited_ids,
            source_content_map,
            tx_amount_map
        )

        if not grounded:

            return (
                False,
                (
                    f"Ungrounded numeric claim: Amount "
                    f"${amount:,.2f} does not match cited evidence."
                ),
                cited_ids
            )

    # -----------------------------------------------------
    # RULE 4: DATE GROUNDING
    # -----------------------------------------------------

    combined_text = " ".join(
        source_content_map.get(cid, "")
        for cid in cited_ids
    )

    available_dates = set(
        extract_dates(combined_text)
    )

    for date in extract_dates(sentence):

        if date not in available_dates:

            return (
                False,
                f"Ungrounded date: '{date}' does not appear in cited evidence.",
                cited_ids
            )

    return True, None, cited_ids


# =========================================================
# CLAIM CHECK LANGGRAPH NODE
# =========================================================

def claim_check_node(
    state: AlertState
) -> Dict[str, Any]:

    draft_note = state.get("draft_note", "")

    available_ids = collect_available_source_ids(state)

    source_content_map, tx_amount_map = (
        build_source_content_map(state)
    )

    sentences = split_sentences(draft_note)

    now_iso = datetime.now(timezone.utc).isoformat()

    # Empty narrative
    if not sentences:

        return {
            "claims": [],
            "claim_check_passed": False,
            "redraft_count": state.get("redraft_count", 0) + 1,
            "audit_log": state.get("audit_log", []) + [
                {
                    "timestamp": now_iso,
                    "node": "claim_check",
                    "action": "CLAIM_CHECK_FAILED",
                    "details": {
                        "error": "Empty draft note received."
                    }
                }
            ]
        }

    claims: List[ClaimItem] = []

    all_passed = True

    # Validate every sentence
    for sentence in sentences:

        is_valid, error_msg, cited_ids = verify_sentence(
            sentence,
            available_ids,
            source_content_map,
            tx_amount_map
        )

        if not is_valid:
            all_passed = False

        claims.append(
            {
                "sentence": sentence,
                "cited_source_ids": cited_ids,
                "is_valid": is_valid,
                "validation_error": error_msg,
            }
        )

    # Audit log
    audit_entry: AuditEntry = {

        "timestamp": now_iso,

        "node": "claim_check",

        "action": (
            "CLAIM_CHECK_PASSED"
            if all_passed
            else "CLAIM_CHECK_FAILED"
        ),

        "details": {

            "total_sentences": len(sentences),

            "valid_sentences": sum(
                1 for claim in claims
                if claim["is_valid"]
            ),

            "all_passed": all_passed,

            "available_source_ids": sorted(
                available_ids
            ),

            "transaction_amounts": {
                key: str(value)
                for key, value in tx_amount_map.items()
            },

            "failures": [
                claim["validation_error"]
                for claim in claims
                if not claim["is_valid"]
            ]
        }
    }

    updated_redraft_count = (
        state.get("redraft_count", 0)
        if all_passed
        else state.get("redraft_count", 0) + 1
    )

    return {

        "claims": claims,

        "claim_check_passed": all_passed,

        "redraft_count": updated_redraft_count,

        "audit_log": (
            state.get("audit_log", [])
            + [audit_entry]
        )
    }
