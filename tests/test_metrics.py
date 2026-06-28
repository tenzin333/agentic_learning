"""Tests for compute_metrics - verifies the math on data with known answers."""

from metrics import compute_metrics


def test_accuracy_and_parse_failure_rate():
    # 4 cases: 3 correct, 1 parse failure -> accuracy 0.5? No: 2 correct of 4.
    records = [
        {"id": "a", "expected": "billing",   "predicted": "billing"},     # correct
        {"id": "b", "expected": "technical", "predicted": "technical"},   # correct
        {"id": "c", "expected": "order",     "predicted": "general"},     # wrong
        {"id": "d", "expected": "account",   "predicted": "parse_error"}, # parse failure
    ]
    res = compute_metrics(records, "v2", "model-x")

    assert res.total == 4
    assert res.accuracy == 0.5                 # 2 of 4 correct
    assert res.parse_failure_rate == 0.25      # 1 of 4 failed to parse


def test_perfect_run_has_f1_one_for_present_categories():
    records = [
        {"id": "a", "expected": "billing",   "predicted": "billing"},
        {"id": "b", "expected": "technical", "predicted": "technical"},
    ]
    res = compute_metrics(records, "v2", "model-x")

    assert res.accuracy == 1.0
    assert res.per_category["billing"].f1 == 1.0
    assert res.per_category["technical"].f1 == 1.0
    # A category that never appeared scores 0 (and has 0 support), not an error.
    assert res.per_category["order"].support == 0
