
"""
LLM Client and Invocation Wrapper (Role A).

Supports:
1. Deterministic mock responses for offline testing.
2. STRUCTURING, SANCTIONS_MATCH and HIGH_VALUE_TRANSFER scenarios.
3. Sentence-level [SRC:...] citations for Claim Check.
4. Gemini and OpenAI providers.
5. Automatic mock fallback if a live API call fails.
"""

import json
import logging
import re
from typing import Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# SCENARIO DETECTION
# ============================================================


def detect_scenario(prompt: str) -> str:
    """Identify the scenario using actual evidence identifiers."""

    text = str(prompt).lower()

    # High-value transfer
    if any(x in text for x in [
        "tx_9940",
        "cust_3088_kyc",
        "cust_3088_networth",
    ]):
        return "HIGH_VALUE_TRANSFER"

    # Sanctions match
    if any(x in text for x in [
        "wl_hit_syn_001",
        "wl_hit_ofac_01",
        "tx_9105",
        "cust_2055_kyc",
    ]):
        return "SANCTIONS_MATCH"

    # Current structuring test fixture
    if any(x in text for x in [
        "tx_8801",
        "cust_1049_kyc",
        "cust-1049",
        "tx_20011",
        "cust_1001_kyc",
        "cust-1001",
    ]):
        return "STRUCTURING"

    return "UNKNOWN"

def extract_evidence_source_ids(prompt: str) -> dict:
    """
    Extract actual evidence source IDs from the current prompt.
    Never invent customer, transaction, policy or watchlist IDs.
    """

    source_pattern = re.compile(
        r"\b(?:CUST|TX|POL|WL)_[A-Z0-9_]+\b",
        re.IGNORECASE
    )

    matches = source_pattern.findall(str(prompt))

    source_ids = list(dict.fromkeys(matches))

    return {
        "customer": [
            sid for sid in source_ids
            if sid.upper().startswith("CUST_")
        ],
        "transactions": [
            sid for sid in source_ids
            if sid.upper().startswith("TX_")
        ],
        "policy": [
            sid for sid in source_ids
            if sid.upper().startswith("POL_")
        ],
        "watchlist": [
            sid for sid in source_ids
            if sid.upper().startswith("WL_")
        ]
    }


def make_source_citation(source_ids: list) -> str:
    """Build a citation using only retrieved source IDs."""

    unique_ids = list(dict.fromkeys(source_ids))

    if not unique_ids:
        return ""

    return "[SRC:" + ", ".join(unique_ids) + "]"

# ============================================================
# MOCK LLM
# ============================================================

def mock_llm_response(
    prompt: str,
    json_mode: bool = False
) -> str:

    lower = str(prompt).lower()
    scenario = detect_scenario(prompt)
    sources = extract_evidence_source_ids(prompt)

    # --------------------------------------------------------
    # 1. CLASSIFICATION
    # --------------------------------------------------------

    if json_mode and "typology" in lower:

        return json.dumps({
            "typology": (
                scenario if scenario != "UNKNOWN"
                else "STRUCTURING"
            ),
            "confidence": 0.95,
            "reasoning": (
                "Classification based on supplied investigation evidence."
            )
        })

    # --------------------------------------------------------
    # 2. VERIFIER
    # --------------------------------------------------------

    if json_mode and (
        "skeptic" in lower or "auditor" in lower
    ):

        if scenario == "SANCTIONS_MATCH":

            return json.dumps({
                "agreed": True,
                "skeptic_critique": (
                    "The potential sanctions screening match must not "
                    "be closed by Level 1 and requires senior compliance "
                    "review. The screening result must be described "
                    "according to its actual list type and identity "
                    "attributes."
                ),
                "flaws_found": [],
                "recommended_action": "ESCALATE_TO_SENIOR"
            })

        if scenario == "HIGH_VALUE_TRANSFER":

            return json.dumps({
                "agreed": True,
                "skeptic_critique": (
                    "The transaction is documented in the supplied "
                    "evidence. Supporting commercial documentation "
                    "and source of funds should be reviewed before "
                    "final disposition."
                ),
                "flaws_found": [],
                "recommended_action": "REVISE"
            })

        if scenario == "STRUCTURING":

            return json.dumps({
                "agreed": True,
                "skeptic_critique": (
                    "The four posted cash deposits and their aggregate "
                    "value are supported by transaction records. "
                    "The timing and pattern warrant further assessment "
                    "under the retrieved structuring policy."
                ),
                "flaws_found": [],
                "recommended_action": "PROCEED"
            })

        return json.dumps({
            "agreed": False,
            "skeptic_critique": (
                "The scenario could not be identified from "
                "the available evidence."
            ),
            "flaws_found": [
                "Manual verification is required."
            ],
            "recommended_action": "ESCALATE_TO_SENIOR"
        })

    # --------------------------------------------------------
    # 3. DRAFT NOTE
    # --------------------------------------------------------

    is_draft_request = (
        "draft case narrative" in lower
        or "fincen 5 ws" in lower
        or "customer_evidence" in lower
        or "transaction_evidence" in lower
    )

    if is_draft_request:

        # ====================================================
        # STRUCTURING
        # ====================================================

            if scenario == "STRUCTURING":

                sources = extract_evidence_source_ids(prompt)

            customer_sources = sources["customer"]
            transaction_sources = [
                sid for sid in sources["transactions"]
                if sid.upper() != "TX_ID"
            ]
            policy_sources = [
                sid for sid in sources["policy"]
                if sid.upper() != "POL_STRUCT"
            ]
            watchlist_sources = sources["watchlist"]

            narrative = []

            if customer_sources:
                narrative.append(
                    "WHO: Customer profile records were retrieved "
                    "for the customer under investigation "
                    + make_source_citation(customer_sources) + "."
                )

            if transaction_sources:
                narrative.append(
                    "WHAT: Four cash deposit transaction records "
                    "were retrieved for examination "
                    + make_source_citation(transaction_sources) + "."
                )

                narrative.append(
                    "WHEN: The transaction records contain the "
                    "documented dates of the cash deposits "
                    + make_source_citation(transaction_sources) + "."
                )

                narrative.append(
                    "WHERE: The transaction memos identify branch "
                    "cash deposit locations, including ATM and teller "
                    "references "
                    + make_source_citation(transaction_sources) + "."
                )

            if policy_sources:
                narrative.append(
                    "WHY: The retrieved structuring policy provides "
                    "the institutional framework for assessing "
                    "multiple cash deposits and potential reporting "
                    "evasion "
                    + make_source_citation(policy_sources) + "."
                )

            if watchlist_sources:
                narrative.append(
                    "The watchlist screening evidence is recorded "
                    "separately and does not establish a confirmed "
                    "regulatory-list match "
                    + make_source_citation(watchlist_sources) + "."
                )

            if not narrative:
                logger.error(
                    "Structuring narrative could not be generated: "
                    "no valid evidence sources were extracted."
                )
                return (
                    "Investigation narrative unavailable pending "
                    "manual review."
                )

            return "\n".join(narrative)


        # ====================================================
        # SANCTIONS MATCH
        # ====================================================

    if scenario == "SANCTIONS_MATCH":

                    if "wl_hit_syn_001" in lower:

                        return "\n".join([

                    (
                        "WHO: The investigation concerns customer "
                        "CUST-2055, whose customer profile was "
                        "retrieved for review [SRC:CUST_2055_KYC]."
                    ),

                    (
                        "WHAT: An outgoing wire transfer of $15,000 "
                        "was recorded under transaction TX-9105 "
                        "[SRC:TX_9105]."
                    ),

                    (
                        "WHEN: The transaction was recorded on "
                        "2026-11-01 [SRC:TX_9105]."
                    ),

                    (
                        "WHERE: The transfer was directed to "
                        "Levant Maritime Logistics LLC and the "
                        "transaction memo states parts logistics "
                        "[SRC:TX_9105]."
                    ),

                    (
                        "WHY: Screening identified a potential match "
                        "on a synthetic internal restricted list, "
                        "with a match score of 98.8%, name similarity "
                        "of 93.8%, a date-of-birth match and no "
                        "country match [SRC:WL_HIT_SYN_001]."
                    ),

                    (
                        "The screening result represents a potential "
                        "internal-list match and does not establish "
                        "a confirmed OFAC SDN match "
                        "[SRC:WL_HIT_SYN_001]."
                    ),

                    (
                        "The retrieved sanctions policy prohibits "
                        "automated closure for matches exceeding "
                        "its documented 80% threshold "
                        "[SRC:POL_SANCT_01]."
                    ),

                    (
                        "The recommended disposition is ESCALATE_L2 "
                        "and referral to the designated sanctions "
                        "officer for further review "
                        "[SRC:POL_SANCT_01]."
                    )

                ])

    return "\n".join([

                (
                    "WHO: The investigation concerns customer "
                    "CUST-2055 [SRC:CUST_2055_KYC]."
                ),

                (
                    "WHAT: An outgoing wire transfer of $15,000 "
                    "was recorded under transaction TX-9105 "
                    "[SRC:TX_9105]."
                ),

                (
                    "WHEN: The transaction was recorded on "
                    "2026-11-01 [SRC:TX_9105]."
                ),

                (
                    "WHERE: The transfer was directed to "
                    "Levant Maritime Logistics LLC [SRC:TX_9105]."
                ),

                (
                    "WHY: The retrieved screening evidence identifies "
                    "a potential sanctions-list match requiring "
                    "human verification [SRC:WL_HIT_OFAC_01]."
                ),

                (
                    "The applicable sanctions policy prohibits "
                    "automated closure above its documented "
                    "80% match threshold [SRC:POL_SANCT_01]."
                ),

                (
                    "The recommended disposition is ESCALATE_L2 "
                    "under the sanctions policy [SRC:POL_SANCT_01]."
                )

            ])

        # ====================================================
        # HIGH VALUE TRANSFER
        # ====================================================

    if scenario == "HIGH_VALUE_TRANSFER":

                    return "\n".join([

                (
                    "WHO: The retrieved customer profile identifies "
                    "Dr. Elena Rostova as Chief of Neurosurgery "
                    "[SRC:CUST_3088_KYC]."
                ),

                (
                    "WHAT: An outgoing wire transfer of $250,000 "
                    "was initiated to First American Title and "
                    "Escrow Co for commercial purchase escrow "
                    "[SRC:TX_9940]."
                ),

                (
                    "WHEN: The transaction was recorded on "
                    "2026-10-25 [SRC:TX_9940]."
                ),

                (
                    "WHERE: The transaction was directed to "
                    "First American Title and Escrow Co "
                    "[SRC:TX_9940]."
                ),

                (
                    "WHY: The retrieved customer profile contains "
                    "professional net-worth information relevant "
                    "to assessing the transaction volume "
                    "[SRC:CUST_3088_NETWORTH]."
                ),

                (
                    "The institutional high-value transaction policy "
                    "requires review of the customer profile and "
                    "supporting transaction rationale "
                    "[SRC:POL_HVT_01]."
                ),

                (
                    "The recommended disposition is REQUEST_RFI "
                    "under the institutional high-value transaction "
                    "policy [SRC:POL_HVT_01]."
                ),

                (
                    "Supporting commercial purchase documentation "
                    "should be obtained and reviewed before "
                    "determining the final disposition "
                    "[SRC:POL_HVT_01]."
                )

            ])

    # --------------------------------------------------------
    # 4. UNKNOWN SCENARIO
    # --------------------------------------------------------

    logger.warning(
        "Mock LLM could not identify a supported scenario."
    )

    if json_mode:

        return json.dumps({
            "agreed": False,
            "skeptic_critique": (
                "The scenario could not be identified from "
                "the supplied evidence."
            ),
            "flaws_found": [
                "Manual review is required."
            ],
            "recommended_action": "ESCALATE_TO_SENIOR"
        })

    return (
        "The investigation scenario could not be identified "
        "from the supplied evidence; manual review is required."
    )


# ============================================================
# TOKEN ESTIMATION
# ============================================================

def estimate_tokens(text: str) -> int:

    return max(1, len(str(text)) // 4)


# ============================================================
# MAIN LLM INVOCATION
# ============================================================

def call_llm(
    prompt: str,
    system_prompt: Optional[str] = None,
    json_mode: bool = False,
) -> Tuple[str, int, int]:

    provider = str(settings.LLM_PROVIDER).lower()
    api_key = settings.LLM_API_KEY

    # --------------------------------------------------------
    # MOCK MODE
    # --------------------------------------------------------

    if provider == "mock" or not api_key:

        response_text = mock_llm_response(
            prompt,
            json_mode=json_mode
        )

        return (
            response_text,
            estimate_tokens(prompt),
            estimate_tokens(response_text)
        )

    # --------------------------------------------------------
    # GEMINI
    # --------------------------------------------------------

    try:

        if provider == "gemini":

            from google import genai

            client = genai.Client(api_key=api_key)

            config_args = {}

            if json_mode:
                config_args["response_mime_type"] = "application/json"

            if system_prompt:
                config_args["system_instruction"] = system_prompt

            response = client.models.generate_content(
                model=settings.LLM_MODEL,
                contents=prompt,
                config=config_args or None
            )

            response_text = response.text or ""

            usage = getattr(
                response,
                "usage_metadata",
                None
            )

            input_tokens = getattr(
                usage,
                "prompt_token_count",
                estimate_tokens(prompt)
            )

            output_tokens = getattr(
                usage,
                "candidates_token_count",
                estimate_tokens(response_text)
            )

            return (
                response_text,
                input_tokens,
                output_tokens
            )

        # ----------------------------------------------------
        # OPENAI
        # ----------------------------------------------------

        if provider == "openai":

            from openai import OpenAI

            client = OpenAI(api_key=api_key)

            messages = []

            if system_prompt:

                messages.append({
                    "role": "system",
                    "content": system_prompt
                })

            messages.append({
                "role": "user",
                "content": prompt
            })

            kwargs = {
                "model": settings.LLM_MODEL,
                "messages": messages,
                "temperature": settings.LLM_TEMPERATURE
            }

            if json_mode:

                kwargs["response_format"] = {
                    "type": "json_object"
                }

            response = client.chat.completions.create(
                **kwargs
            )

            response_text = (
                response.choices[0].message.content or ""
            )

            usage = response.usage

            input_tokens = (
                usage.prompt_tokens
                if usage
                else estimate_tokens(prompt)
            )

            output_tokens = (
                usage.completion_tokens
                if usage
                else estimate_tokens(response_text)
            )

            return (
                response_text,
                input_tokens,
                output_tokens
            )

        logger.warning(
            "Unknown LLM provider '%s'. Using mock fallback.",
            provider
        )

    except Exception as exc:

        logger.warning(
            "Live LLM invocation failed for %s: %s. "
            "Using deterministic mock fallback.",
            provider,
            exc
        )

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    fallback_response = mock_llm_response(
        prompt,
        json_mode=json_mode
    )

    return (
        fallback_response,
        estimate_tokens(prompt),
        estimate_tokens(fallback_response)
    )
