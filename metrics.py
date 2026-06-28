"""Quality metrics for an evaluation run.

Takes the per-case predictions produced by ``evaluate.py`` and turns them into a
typed, serializable ``EvalResult``: overall accuracy, per-category
precision/recall/F1, a confusion matrix, and the parse-failure rate. These
snapshots are what the regression detector (Phase 2) diffs against a baseline.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from pydantic import BaseModel
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)

# The valid labels the classifier is allowed to emit. "parse_error" is tracked
# separately (see parse_failure_rate) rather than treated as a real category.
VALID_CATEGORIES = ["billing", "technical", "account", "order", "general", "unknown"]
PARSE_ERROR = "parse_error"


class CasePrediction(BaseModel):
    id: str
    expected: str
    predicted: str
    correct: bool


class CategoryMetrics(BaseModel):
    precision: float
    recall: float
    f1: float
    support: int


class ConfusionMatrix(BaseModel):
    labels: list[str]
    matrix: list[list[int]]


class EvalResult(BaseModel):
    prompt_version: str
    model: str
    timestamp: str
    total: int
    accuracy: float
    parse_failure_rate: float
    per_category: dict[str, CategoryMetrics]
    confusion: ConfusionMatrix
    predictions: list[CasePrediction]

    def save(self, results_dir: str = "results") -> str:
        """Write this result to ``results/<prompt>__<model>__<ts>.json`` and return the path."""
        os.makedirs(results_dir, exist_ok=True)
        safe_model = self.model.replace("/", "_").replace(":", "_")
        safe_ts = self.timestamp.replace(":", "-")
        path = os.path.join(results_dir, f"{self.prompt_version}__{safe_model}__{safe_ts}.json")
        with open(path, "w") as f:
            json.dump(self.model_dump(), f, indent=2)
        return path


def compute_metrics(
    records: list[dict],
    prompt_version: str,
    model: str,
    categories: list[str] = VALID_CATEGORIES,
) -> EvalResult:
    """Build an EvalResult from per-case records.

    Each record must have keys: ``id``, ``expected``, ``predicted``.
    """
    y_true = [r["expected"] for r in records]
    y_pred = [r["predicted"] for r in records]
    total = len(records)

    accuracy = float(accuracy_score(y_true, y_pred)) if total else 0.0
    parse_failures = sum(1 for p in y_pred if p == PARSE_ERROR)
    parse_failure_rate = parse_failures / total if total else 0.0

    # Per-category precision/recall/F1 over the valid label set. zero_division=0
    # so categories absent from this run report 0 instead of raising.
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=categories, zero_division=0
    )
    per_category = {
        cat: CategoryMetrics(
            precision=float(precision[i]),
            recall=float(recall[i]),
            f1=float(f1[i]),
            support=int(support[i]),
        )
        for i, cat in enumerate(categories)
    }

    # Confusion matrix over every label that actually appears (valid categories
    # plus any stray predictions like parse_error), so nothing is silently dropped.
    seen = [c for c in categories if c in y_true or c in y_pred]
    extras = sorted({p for p in y_pred if p not in categories})
    cm_labels = seen + extras
    cm = confusion_matrix(y_true, y_pred, labels=cm_labels).tolist()

    return EvalResult(
        prompt_version=prompt_version,
        model=model,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        total=total,
        accuracy=accuracy,
        parse_failure_rate=parse_failure_rate,
        per_category=per_category,
        confusion=ConfusionMatrix(labels=cm_labels, matrix=cm),
        predictions=[
            CasePrediction(
                id=r["id"],
                expected=r["expected"],
                predicted=r["predicted"],
                correct=r["expected"] == r["predicted"],
            )
            for r in records
        ],
    )


def format_report(result: EvalResult) -> str:
    """Render an EvalResult as a human-readable console report."""
    lines = [
        "",
        f"Prompt: {result.prompt_version}   Model: {result.model}",
        f"Accuracy: {result.accuracy:.1%}   "
        f"Parse failures: {result.parse_failure_rate:.1%}   "
        f"(n={result.total})",
        "",
        f"  {'category':10s} {'precision':>9s} {'recall':>7s} {'f1':>7s} {'support':>8s}",
        f"  {'-' * 10} {'-' * 9} {'-' * 7} {'-' * 7} {'-' * 8}",
    ]
    for cat, m in result.per_category.items():
        lines.append(
            f"  {cat:10s} {m.precision:9.2f} {m.recall:7.2f} {m.f1:7.2f} {m.support:8d}"
        )
    return "\n".join(lines)
