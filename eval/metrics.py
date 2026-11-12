"""Evaluation Metrics Engine for AML Alert Investigator (Role A).
Defines quantitative evaluation metrics for banking compliance benchmarks:
1. Groundedness Rate (% of claims verified by deterministic claim check)
2. Citation Precision (% of cited source IDs existing in ground truth evidence)
3. Decision Accuracy, Precision, Recall, Macro/Weighted F1, and Confusion Matrix vs ground truth labels
4. Human Override Rate (% of cases where the analyst modified agent recommendation)
5. Execution Telemetry (p95 latency, average latency, token count, cost per case)
"""

from typing import Any, Dict, List, Optional, Set


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
) -> Dict[str, Any]:
    """Calculates Precision, Recall, F1 Score, Accuracy, Macro/Weighted F1,
    per-class breakdown, and confusion matrix for decisions.
    """
    if not predictions or len(predictions) != len(ground_truth):
        return {
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "macro_f1": 0.0,
            "weighted_f1": 0.0,
            "total_cases": 0,
            "per_class": {},
            "confusion_matrix": {},
        }

    total = len(predictions)
    correct = sum(1 for p, g in zip(predictions, ground_truth) if p == g)
    accuracy = round(correct / total, 4)

    # Binary metrics for positive_label (backward compatibility)
    tp = sum(1 for p, g in zip(predictions, ground_truth) if p == positive_label and g == positive_label)
    fp = sum(1 for p, g in zip(predictions, ground_truth) if p == positive_label and g != positive_label)
    fn = sum(1 for p, g in zip(predictions, ground_truth) if p != positive_label and g == positive_label)

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    f1 = round(2 * (precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0

    # Multi-class breakdown & confusion matrix
    all_classes = sorted(list(set(ground_truth) | set(predictions)))
    per_class: Dict[str, Dict[str, Any]] = {}
    confusion_matrix: Dict[str, Dict[str, int]] = {
        actual: {pred: 0 for pred in all_classes} for actual in all_classes
    }

    for p, g in zip(predictions, ground_truth):
        confusion_matrix[g][p] = confusion_matrix[g].get(p, 0) + 1

    for c in all_classes:
        c_tp = sum(1 for p, g in zip(predictions, ground_truth) if p == c and g == c)
        c_fp = sum(1 for p, g in zip(predictions, ground_truth) if p == c and g != c)
        c_fn = sum(1 for p, g in zip(predictions, ground_truth) if p != c and g == c)
        c_support = sum(1 for g in ground_truth if g == c)

        c_prec = round(c_tp / (c_tp + c_fp), 4) if (c_tp + c_fp) > 0 else 0.0
        c_rec = round(c_tp / (c_tp + c_fn), 4) if (c_tp + c_fn) > 0 else 0.0
        c_f1 = round(2 * (c_prec * c_rec) / (c_prec + c_rec), 4) if (c_prec + c_rec) > 0 else 0.0

        per_class[c] = {
            "precision": c_prec,
            "recall": c_rec,
            "f1": c_f1,
            "support": c_support,
        }

    macro_f1 = round(sum(d["f1"] for d in per_class.values()) / len(all_classes), 4) if all_classes else 0.0
    weighted_f1 = (
        round(sum(d["f1"] * d["support"] for d in per_class.values()) / total, 4)
        if total > 0
        else 0.0
    )

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "total_cases": total,
        "per_class": per_class,
        "confusion_matrix": confusion_matrix,
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
    """Aggregates cost, token consumption, and latency telemetry across an evaluation run."""
    if not eval_cases:
        return {
            "avg_tokens": 0.0,
            "avg_cost_usd": 0.0,
            "total_cost_usd": 0.0,
            "avg_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "max_latency_ms": 0.0,
        }

    total_tokens = sum(c.get("total_tokens_used", 0) for c in eval_cases)
    total_cost = sum(c.get("estimated_cost_usd", 0.0) for c in eval_cases)
    count = len(eval_cases)

    latencies = [
        float(c.get("execution_latency_ms") or c.get("latency_ms") or 0.0)
        for c in eval_cases
    ]
    latencies.sort()

    if latencies:
        avg_latency = round(sum(latencies) / len(latencies), 2)
        p95_idx = int(0.95 * len(latencies))
        p95_latency = round(latencies[min(p95_idx, len(latencies) - 1)], 2)
        max_latency = round(latencies[-1], 2)
    else:
        avg_latency = 0.0
        p95_latency = 0.0
        max_latency = 0.0

    return {
        "avg_tokens": round(total_tokens / count, 1),
        "avg_cost_usd": round(total_cost / count, 5),
        "total_cost_usd": round(total_cost, 4),
        "avg_latency_ms": avg_latency,
        "p95_latency_ms": p95_latency,
        "max_latency_ms": max_latency,
    }
