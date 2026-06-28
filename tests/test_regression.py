"""Tests for the regression decision logic - formalizes the old reg_check.py."""

from metrics import compute_metrics
from regression import compare, is_regression


# --- is_regression: the per-metric, direction-aware decision ------------------

def test_real_drop_is_regression():
    # accuracy fell 0.06 with tolerance 0.03 -> regression.
    assert is_regression(0.90, 0.84, 0.03, higher_is_better=True) is True


def test_noise_below_tolerance_is_not_regression():
    # fell only 0.01 -> within the noise floor -> not a regression.
    assert is_regression(0.90, 0.89, 0.03, higher_is_better=True) is False


def test_improvement_is_not_regression():
    assert is_regression(0.90, 0.95, 0.03, higher_is_better=True) is False


def test_rising_failure_rate_is_regression():
    # for parse_failure_rate, LOWER is better, so a RISE is the bad direction.
    assert is_regression(0.10, 0.20, 0.03, higher_is_better=False) is True


# --- compare: roll the per-metric decision up into a report -------------------

def _result(records, version="v"):
    return compute_metrics(records, version, "model-x")


def test_compare_flags_localized_category_regression():
    # Same accuracy story, but one category breaks -> compare must FAIL and
    # name the flipped case.
    base = _result([
        {"id": "billing_01", "expected": "billing", "predicted": "billing"},
        {"id": "order_01",   "expected": "order",   "predicted": "order"},
    ])
    cand = _result([
        {"id": "billing_01", "expected": "billing", "predicted": "billing"},
        {"id": "order_01",   "expected": "order",   "predicted": "general"},  # broke
    ])

    report = compare(base, cand, tolerance=0.03)

    assert report.passed is False
    assert report.flipped == ["order_01"]


def test_compare_passes_when_identical():
    records = [{"id": "billing_01", "expected": "billing", "predicted": "billing"}]
    report = compare(_result(records), _result(records), tolerance=0.03)
    assert report.passed is True
    assert report.flipped == []
