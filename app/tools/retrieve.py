"""Policy retrieval with stable source IDs and an offline lexical fallback."""
import re
from pathlib import Path
from typing import Dict, List

POLICY_DIR = Path(__file__).resolve().parents[2] / "data" / "policies"
PREFIX = {
    "aml_structuring_policy.md": "POL_STRUCT",
    "aml_sanctions_policy.md": "POL_SANCT",
    "aml_high_value_policy.md": "POL_HVT",
    "customer_due_diligence_policy.md": "POL_KYC",
    "evidence_quality_policy.md": "POL_EVIDENCE",
    "human_escalation_policy.md": "POL_ESCALATE",
}

def _tokens(text: str):
    return set(re.findall(r"[a-z0-9]+", text.lower()))

def load_policy_chunks() -> List[Dict[str, str]]:
    chunks = []
    for filename, prefix in PREFIX.items():
        path = POLICY_DIR / filename
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        # One stable chunk per policy document for this first demo iteration.
        chunks.append({"source_id": f"{prefix}_01", "title": path.stem.replace("_"," ").title(),
                       "content": content})
    return chunks

def retrieve_policy(query: str, top_k: int = 3) -> List[Dict[str, str]]:
    query_tokens = _tokens(query)
    scored = []
    for chunk in load_policy_chunks():
        score = len(query_tokens & _tokens(chunk["content"]))
        scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for score, chunk in scored[:top_k] if score > 0] or load_policy_chunks()[:top_k]
