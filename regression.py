"""Regression detection: compare a candidate EvalResult against a baseline.

The flow: load a blessed baseline snapshot, run `compare()` against a fresh
candidate, and get a RegressionReport. If any watched metric got worse by more
than `tolerance`, the report fails — which the CLI turns into a non-zero exit
code so CI can block the merge.
"""

import json

from pydantic import BaseModel

from metrics import EvalResult


def is_regression(baseline: float, candidate: float, tolerance: float, higher_is_better: bool) -> bool:
    """
        baseline: known good run metric
        candidate: same metric but from the new run
        tolerance: noise floor, how big a drop you'll forgive before calling it a regression
        higher_is_better:  accuracy & F1 = true, failure = false
    """
    delta = candidate - baseline
    # if higher_is_better, NEGATIVE delta
    if higher_is_better:
        return delta < -tolerance  # regressed if it dropped by more than tolerance
    else:
        return delta > tolerance  # regressed if it rose by more than tolerance


class MetricDelta(BaseModel):
    name: str          # "accuracy", "parse_failure_rate", "f1[billing]"
    baseline: float
    candidate: float
    delta: float       # candidate - baseline
    regressed: bool


class RegressionReport(BaseModel):
    passed: bool                 # False if ANY metric regressed
    tolerance: float
    deltas: list[MetricDelta]
    flipped: list[str]           # case ids correct in baseline but wrong now


def flipped_cases(baseline: EvalResult, candidate: EvalResult) -> list[str]:
    """Case ids that were correct in the baseline but became wrong in the candidate.

    This is the 'what actually broke' detail: per-metric numbers tell you a
    category slipped, but flipped cases name the exact emails to go look at.
    """
    base_correct = {p.id: p.correct for p in baseline.predictions}
    return [
        p.id
        for p in candidate.predictions
        if base_correct.get(p.id) is True and not p.correct
    ]


def compare(baseline: EvalResult, candidate: EvalResult, tolerance: float = 0.03) -> RegressionReport:
    """Compare every watched metric and produce a pass/fail report."""
    # Build one flat checklist of (name, baseline_value, candidate_value, higher_is_better).
    # Every metric is the same shape, so we can judge them all in one loop.
    checks: list[tuple[str, float, float, bool]] = [
        ("accuracy", baseline.accuracy, candidate.accuracy, True),
        ("parse_failure_rate", baseline.parse_failure_rate, candidate.parse_failure_rate, False),
    ]
    for cat in baseline.per_category:
        b_f1 = baseline.per_category[cat].f1
        c_f1 = candidate.per_category[cat].f1
        checks.append((f"f1[{cat}]", b_f1, c_f1, True))

    deltas = [
        MetricDelta(
            name=name,
            baseline=b,
            candidate=c,
            delta=c - b,
            regressed=is_regression(b, c, tolerance, higher_is_better),
        )
        for name, b, c, higher_is_better in checks
    ]

    passed = not any(d.regressed for d in deltas)
    return RegressionReport(
        passed=passed,
        tolerance=tolerance,
        deltas=deltas,
        flipped=flipped_cases(baseline, candidate),
    )


def load_baseline(path: str = "baselines/baseline.json") -> EvalResult:
    with open(path) as f:
        return EvalResult.model_validate(json.load(f))


def format_regression_report(report: RegressionReport) -> str:
    """Render a RegressionReport as a human-readable diff table."""
    verdict = "PASS - no regression" if report.passed else "FAIL - regression detected"
    lines = [
        "",
        f"Regression check: {verdict}  (tolerance={report.tolerance})",
        "",
        f"  {'metric':22s} {'baseline':>9s} {'candidate':>9s} {'delta':>8s}  flag",
        f"  {'-' * 22} {'-' * 9} {'-' * 9} {'-' * 8}  ----",
    ]
    for d in report.deltas:
        flag = "REGRESSED" if d.regressed else ""
        lines.append(
            f"  {d.name:22s} {d.baseline:9.3f} {d.candidate:9.3f} {d.delta:+8.3f}  {flag}"
        )
    if report.flipped:
        lines.append("")
        lines.append(f"  Flipped cases (were correct, now wrong): {', '.join(report.flipped)}")
    return "\n".join(lines)
