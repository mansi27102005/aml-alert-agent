"""Tests for Evaluation Metrics and Chaos Test Suite (Role A).
"""

from eval.chaos_cases import run_all_chaos_tests
from eval.metrics import (
    calculate_citation_precision,
    calculate_classification_metrics,
    calculate_groundedness_rate,
    calculate_human_override_rate,
    calculate_telemetry_summary,
)


def test_metrics_groundedness_rate():
    claims = [
        {"sentence": "Sentence 1", "is_valid": True},
        {"sentence": "Sentence 2", "is_valid": True},
        {"sentence": "Sentence 3", "is_valid": False},
        {"sentence": "Sentence 4", "is_valid": True},
    ]
    rate = calculate_groundedness_rate(claims)
    assert rate == 0.75


def test_metrics_citation_precision():
    claims = [
        {"cited_source_ids": ["POL_01", "TX_01"]},
        {"cited_source_ids": ["TX_02", "GHOST_99"]},
    ]
    available_ids = {"POL_01", "TX_01", "TX_02"}
    precision = calculate_citation_precision(claims, available_ids)
    assert precision == 0.75


def test_metrics_classification_metrics():
    preds = ["FILE_SAR", "CLOSE_FALSE_POSITIVE", "FILE_SAR", "CLOSE_FALSE_POSITIVE"]
    truths = ["FILE_SAR", "CLOSE_FALSE_POSITIVE", "CLOSE_FALSE_POSITIVE", "CLOSE_FALSE_POSITIVE"]
    res = calculate_classification_metrics(preds, truths, positive_label="FILE_SAR")
    assert res["accuracy"] == 0.75
    assert res["precision"] == 0.5
    assert res["recall"] == 1.0


def test_metrics_telemetry_summary():
    cases = [
        {"total_tokens_used": 1000, "estimated_cost_usd": 0.002},
        {"total_tokens_used": 2000, "estimated_cost_usd": 0.004},
    ]
    summary = calculate_telemetry_summary(cases)
    assert summary["avg_tokens"] == 1500.0
    assert summary["total_cost_usd"] == 0.006


def test_chaos_suite_resilience():
    results = run_all_chaos_tests()
    assert len(results) == 4
    assert all(r["passed"] for r in results)

