# LLM Regression CI

> A CI/CD quality gate that catches LLM prompt/model regressions before they ship.

A CI/CD-style quality gate for LLM-powered features. It evaluates a prompt (or model)
against a **golden dataset**, measures quality with real classification metrics, and
**fails the build + alerts Slack when quality regresses** — so a bad prompt never reaches
production.

The reference feature under test is a **customer-support email classifier** (categorises an
email as `billing` / `technical` / `account` / `order` / `general` and returns structured JSON),
but the pipeline is feature-agnostic: swap the golden set and prompt and it works for any
classify/extract task.

---

## Why this exists

Prompts and models are invisible dependencies. Tweaking a prompt to fix one case can silently
break three others, and a single "accuracy" number hides it: overall accuracy can stay flat
while one category quietly collapses. This project treats **prompts as code** and runs a
**regression test on every change**, the same way you'd guard application logic with CI.

---

## How it works

```
                    prompts/v2.yaml ──┐
                                      │
 tests/ground_truth.yaml ──► evaluate.py ──► metrics.py ──► EvalResult (JSON)
   (golden labels)            (run LLM)      (P/R/F1,          │
                                              confusion,       ▼
                                              parse-rate)   regression.py ──► pass/fail
                                                               ▲              (exit 0/1)
                              baselines/baseline.json ─────────┘                  │
                              (committed "known good")                            ▼
                                                                    cli.py check ──► Slack alert
                                                                                    + CI red ✗
```

- **`evaluate.py`** runs the prompt over every email in the golden set and records predictions.
- **`metrics.py`** turns predictions into a typed `EvalResult`: overall accuracy, **per-category
  precision / recall / F1**, a confusion matrix, and the **parse-failure rate** (how often the
  model broke its JSON contract).
- **`regression.py`** compares a candidate `EvalResult` against a committed **baseline**. A metric
  counts as regressed only if it moved in the bad direction by **more than a tolerance** (LLMs are
  non-deterministic, so a noise floor avoids false alarms). It also reports the exact **flipped
  cases** (correct before, wrong now).
- **`cli.py`** exposes `check` (exit `1` on regression) and `update-baseline`. The exit code is the
  contract with CI.
- **`alert.py`** posts to a Slack webhook on regression; a graceful no-op when no webhook is set.
- **`.github/workflows/eval.yml`** runs `check` on every PR that touches a prompt, the golden set,
  or the code — turning a regression into a blocked merge.

---

## Demo: a regression being caught

Sabotage a prompt (e.g. `prompts/v3.yaml` that always answers `general`) and check it:

```console
$ python cli.py check --prompt v3

Regression check: FAIL - regression detected  (tolerance=0.03)

  metric                  baseline candidate    delta  flag
  ---------------------- --------- --------- --------  ----
  accuracy                   1.000     0.750   -0.250  REGRESSED
  parse_failure_rate         0.000     0.000   +0.000
  f1[billing]                1.000     1.000   +0.000
  f1[order]                  1.000     0.000   -1.000  REGRESSED
  ...

  Flipped cases (were correct, now wrong): order_01

$ echo $?
1            # non-zero exit -> CI fails the PR, Slack alert fires
```

Notice what the report surfaces that a bare accuracy number would not: **which category broke**
(`f1[order]` → 0.0) and **which exact email caused it** (`order_01`).

---

## Quick start

```bash
python -m venv venv && source venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt

# configure secrets (see .env.example)
cp .env.example .env        # then fill in MODEL + HUGGING_FACE_API_KEY

# 1. bless a known-good prompt as the baseline, then commit baselines/baseline.json
python cli.py update-baseline --prompt v2

# 2. check a change against that baseline (exit 1 if it regressed)
python cli.py check --prompt v2

# run the fast, offline unit tests
pytest tests/
```

---

## Design decisions

- **Committed baselines, never regenerated in CI.** The baseline is a git-tracked snapshot of
  "acceptable quality." CI only *reads* it (`permissions: contents: read`) and compares against it.
  If CI regenerated the baseline each run, the candidate would always equal the baseline and
  nothing could ever fail. Raising the bar is a deliberate, reviewed act: `update-baseline` locally,
  then commit.
- **Tolerance over exact match.** LLM output is non-deterministic, so the same prompt wiggles a
  point or two between runs. A configurable `--tolerance` (default 0.03) separates real regressions
  from sampling noise.
- **Per-category F1, not just accuracy.** Localized failures (one category collapsing) are invisible
  to overall accuracy. F1 per category is what makes the gate trustworthy.
- **Two-speed CI.** Unit tests are fully offline and mock-free (the logic is pure functions, I/O lives
  at the edges), so they run on every push for free. The expensive live-LLM evaluation only runs when
  a prompt, the golden set, or the code actually changes.
- **Graceful degradation.** Missing Slack webhook → alerts no-op with a printed warning instead of
  crashing; a Slack outage soft-fails so it can never take down the regression check itself.

---

## Project layout

```
prompts/                versioned prompt configs (v1, v2, ...) with few-shot examples
tests/ground_truth.yaml golden dataset: labeled emails (the "test cases")
tests/test_*.py         offline unit tests (parse, metrics, regression)
evaluate.py             run a prompt over the golden set
metrics.py              EvalResult + accuracy / P-R-F1 / confusion / parse-rate
regression.py           baseline-vs-candidate comparison + exit code
alert.py                Slack webhook notifier (graceful no-op)
cli.py                  `check` / `update-baseline` entrypoints
utils/model_utils.py    robust JSON extraction from messy model output
baselines/baseline.json committed "known good" reference (created by update-baseline)
.github/workflows/      CI: run the regression check on PRs
```

---

## Tech

Python · LangChain (Hugging Face inference) · scikit-learn (metrics) · Pydantic (typed results) ·
pytest · GitHub Actions · Slack webhooks.
