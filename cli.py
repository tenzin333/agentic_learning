"""Command-line entrypoint for the regression detection pipeline.

Two commands:
    python cli.py update-baseline --prompt v2   # bless a run as the quality bar
    python cli.py check           --prompt v3   # fail (exit 1) if v3 regresses vs baseline

The `check` command's exit code is the contract with CI: 0 = passed, 1 = regression.
CI reads that code (not the printed table) to decide whether to block a merge.
"""

import argparse
import json
import os
import sys

from evaluate import run_evaluation
from regression import compare, format_regression_report, load_baseline
from dotenv import load_dotenv
from alert import SlackAlerter

load_dotenv()
BASELINE_PATH = "baselines/baseline.json"


def cmd_check(args: argparse.Namespace) -> None:
    """Run the candidate prompt and fail if it regressed against the baseline."""
    baseline = load_baseline(BASELINE_PATH)          # the blessed "known good" snapshot
    candidate = run_evaluation(args.prompt)          # fresh run (also saves a results/ snapshot)

    report = compare(baseline, candidate, tolerance=args.tolerance)
    print(format_regression_report(report))

    if not report.passed:
        alerter = SlackAlerter(os.getenv("SLACK_WEBHOOK_URL"))
        regressed = [d.name for d in report.deltas if d.regressed]
        alerter.error(
            f"Regression in '{args.prompt}': {', '.join(regressed)} "
            f"(flipped: {', '.join(report.flipped) or 'none'})"
        )
    
    # The whole reason the CLI exists: translate pass/fail into an exit code CI can read.
    sys.exit(0 if report.passed else 1)


def cmd_update_baseline(args: argparse.Namespace) -> None:
    """Run a prompt and store its result as the new baseline to compare future runs against."""
    result = run_evaluation(args.prompt)

    os.makedirs(os.path.dirname(BASELINE_PATH), exist_ok=True)
    with open(BASELINE_PATH, "w") as f:
        json.dump(result.model_dump(), f, indent=2)
    print(f"\nBaseline updated -> {BASELINE_PATH} "
          f"(prompt={result.prompt_version}, accuracy={result.accuracy:.1%})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="emailclf",
        description="Evaluate prompts against a golden set and detect regressions.",
    )
    # Subcommands: each gets its own name, its own args, and its own handler function.
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="run a prompt and exit 1 if it regresses vs baseline")
    p_check.add_argument("--prompt", required=True, help="prompt version to test, e.g. v2")
    p_check.add_argument("--tolerance", type=float, default=0.03,
                         help="how big a metric drop to forgive as noise (default 0.03)")
    p_check.set_defaults(func=cmd_check)

    p_update = sub.add_parser("update-baseline", help="run a prompt and save it as the new baseline")
    p_update.add_argument("--prompt", required=True, help="prompt version to bless, e.g. v2")
    p_update.set_defaults(func=cmd_update_baseline)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)   # dispatch to whichever cmd_* the chosen subcommand registered


if __name__ == "__main__":
    main()
