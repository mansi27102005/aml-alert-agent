"""Evaluation Metrics Engine for AML Alert Investigator (Role A).
Defines quantitative evaluation metrics for banking compliance benchmarks:
1. Groundedness Rate (% of claims verified by deterministic claim check)
2. Citation Precision (% of cited source IDs existing in ground truth evidence)
3. Decision Accuracy, Precision, Recall, and F1 vs ground truth labels
4. Human Override Rate (% of cases where the analyst modified agent recommendation)
5. Execution Telemetry (p95 latency, average token count, cost per case)
"""

from typing import Any, Dict, List, Optional


def calculate_groundedness_rate(claims: List[Dict[str, Any]]) -> float:
    """Calculates the groundedness rate: valid sentences divided by total sentences.
    Returns a score between 0.0 and 1.0.
    """
    if not claims:
        return 0.0
    valid_count = sum(1 for c in claims if c.get("is_valid", False))
    return round(valid_count / len(claims), 4)


def calculate_citation_precision(claims: List[Dict[str, Any]], available_source_ids: set) -> float:
    """Calculates the proportion of cited source IDs that legitimately exist in evidence."""
    total_citations = 0
    valid_citations = 0

    for c in claims:
        for cid in c.get("cited_source_ids", []):
            total_citations += 1
            if cid.strip().upper() in available_source_ids:
                valid_citations += 1

    if total_citations == 0:
        return 0.0
    return round(valid_citations / total_citations, 4)


def calculate_classification_metrics(
    predictions: List[str],
    ground_truth: List[str],
    positive_label: str = "FILE_SAR",
) -> Dict[str, float]:
    """Calculates Precision, Recall, F1 Score, and Accuracy for binary or multi-class decisions."""
    if not predictions or len(predictions) != len(ground_truth):
        return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

    total = len(predictions)
    correct = sum(1 for p, g in zip(predictions, ground_truth) if p == g)
    accuracy = round(correct / total, 4)

    tp = sum(1 for p, g in zip(predictions, ground_truth) if p == positive_label and g == positive_label)
    fp = sum(1 for p, g in zip(predictions, ground_truth) if p == positive_label and g != positive_label)
    fn = sum(1 for p, g in zip(predictions, ground_truth) if p != positive_label and g == positive_label)

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    f1 = round(2 * (precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "total_cases": total,
    }


def calculate_human_override_rate(eval_cases: List[Dict[str, Any]]) -> float:
    """Calculates the frequency with which a human analyst edited the drafted note
    or modified the proposed disposition.
    """
    if not eval_cases:
        return 0.0

    overrides = 0
    for case in eval_cases:
        has_edit = bool(case.get("human_edits"))
        override_disp = bool(case.get("disposition_override"))
        if has_edit or override_disp:
            overrides += 1

    return round(overrides / len(eval_cases), 4)


def calculate_telemetry_summary(eval_cases: List[Dict[str, Any]]) -> Dict[str, float]:
    """Aggregates cost and token consumption telemetry across an evaluation run."""
    if not eval_cases:
        return {"avg_tokens": 0.0, "avg_cost_usd": 0.0, "total_cost_usd": 0.0}

    total_tokens = sum(c.get("total_tokens_used", 0) for c in eval_cases)
    total_cost = sum(c.get("estimated_cost_usd", 0.0) for c in eval_cases)
    count = len(eval_cases)

    return {
        "avg_tokens": round(total_tokens / count, 1),
        "avg_cost_usd": round(total_cost / count, 5),
        "total_cost_usd": round(total_cost, 4),
    }
