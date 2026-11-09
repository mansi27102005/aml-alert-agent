"""Verifier Node (Role A).
Executes independent 2nd-Line-of-Defense compliance QA.
Uses an adversarial skeptic prompt to probe the draft narrative for:
1. Unjustified alert closures.
2. Unchecked sanctions hits (>80%).
3. Policy threshold violations and speculative excuses.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict
from app.audit import calculate_token_cost
from app.config import settings
from app.llm import call_llm
from app.state import AlertState, AuditEntry

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "verifier.txt"


def verifier_node(state: AlertState) -> Dict[str, Any]:
    """LangGraph node execution function for the Skeptical Verifier."""
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    # Format Policy Context
    policies = state.get("policy_chunks", [])
    policy_summary = "\n".join(
        [f"- [{p.get('source_id')}]: {p.get('content')}" for p in policies]
    ) or "No policies provided."

    # Format Evidence Summary
    evidence = state.get("evidence", {})
    evidence_summary = json.dumps(
        {tool: data.get("data", {}) for tool, data in evidence.items()},
        indent=2,
    )

    draft_note = state.get("draft_note", "")

    prompt = prompt_template.format(
        policy_context=policy_summary,
        evidence_summary=evidence_summary,
        draft_note=draft_note,
    )

    response_text, in_tok, out_tok = call_llm(prompt, json_mode=True)
    call_cost = calculate_token_cost(in_tok, out_tok, settings.LLM_MODEL)

    agreed = False
    critique = ""
    flaws = []
    action = "ESCALATE_TO_SENIOR"

    try:
        data = json.loads(response_text)
        agreed = bool(data.get("agreed", False))
        critique = str(data.get("skeptic_critique", ""))
        flaws = list(data.get("flaws_found", []))
        action = str(data.get("recommended_action", action))
    except Exception:
        # Fallback parsing
        agreed = "true" in response_text.lower() and "agreed" in response_text.lower()
        critique = response_text[:300]

    now_iso = datetime.now(timezone.utc).isoformat()
    audit_entry: AuditEntry = {
        "timestamp": now_iso,
        "node": "verifier",
        "action": "VERIFICATION_AUDIT_COMPLETED",
        "details": {
            "verifier_agreed": agreed,
            "recommended_action": action,
            "flaws_detected_count": len(flaws),
            "skeptic_critique": critique,
            "tokens_used": in_tok + out_tok,
            "cost_usd": call_cost,
        },
    }

    return {
        "verifier_agreed": agreed,
        "verifier_notes": critique,
        "total_tokens_used": state.get("total_tokens_used", 0) + in_tok + out_tok,
        "estimated_cost_usd": state.get("estimated_cost_usd", 0.0) + call_cost,
        "audit_log": state.get("audit_log", []) + [audit_entry],
    }
