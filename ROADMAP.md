# Roadmap: Model Regression Detection System (Project 1)

## Context
The repo today is a **prompt + golden-dataset + basic eval runner** for a customer-support
email classifier. The actual goal is bigger: a **CI/CD-style pipeline that tests an LLM feature
against a golden dataset whenever a prompt or model changes, detects quality regressions, and
alerts via Slack before bad outputs reach users.**

Gap analysis: the scaffolding exists (golden set `tests/ground_truth.yaml`, versioned prompts
`prompts/v1,v2.yaml`, schema `schema/promptsSchema.py`, a now-debugged `evaluate.py`), but the
three headline capabilities — **regression detection, CI on change, and Slack alerting** — do
not exist yet. The project is ~30% done. This roadmap covers the remaining 70% plus the
engineering polish that makes it CV-ready.

Goal: a recruiter/engineer can clone the repo, read the README, run one command to evaluate a
prompt against a baseline, see a regression caught with metrics, and see the GitHub Actions
check fail + a Slack alert fire on a regressing PR.

---

## Target architecture
```
emailclf/                  # rename loose scripts into a real package
  __init__.py
  classifier.py            # the LLM feature (from main.py) — provider-agnostic call
  schema.py                # PromptConfig, FewShotExample (moved from schema/)
  prompts.py               # load_prompt + build_system_prompt (with few-shot)
  metrics.py               # accuracy, per-category precision/recall/F1, confusion matrix
  evaluate.py              # run feature over golden set -> EvalResult
  regression.py            # compare EvalResult vs baseline -> RegressionReport + exit code
  alert.py                 # Slack webhook notifier (optional, graceful no-op if unset)
  cli.py                   # `python -m emailclf ...` entrypoints
prompts/                   # versioned prompts (exists)
data/golden.yaml           # renamed/expanded from tests/ground_truth.yaml (~30-50 cases)
baselines/baseline.json    # committed baseline metrics the pipeline diffs against
results/                   # per-run metric snapshots (gitignored except baseline)
tests/                     # pytest unit tests (mock the LLM — deterministic, no API cost)
.github/workflows/eval.yml # CI: trigger on prompts/**, data/**, model config changes
pyproject.toml             # packaging + deps + ruff/pytest config
.env.example               # documents required env vars, no secrets
README.md                  # the CV centerpiece: problem, architecture diagram, demo, results
```

---

## Phase 0 — Stabilize (prereq, quick)
- Finish fixing `evaluate.py` (most bugs already fixed). Confirm a clean run.
- **Robust JSON parsing**: models wrap JSON in ```` ```json ```` fences or add prose. Add a
  `parse_model_json()` helper that strips fences and extracts the first balanced `{...}` before
  `json.loads`. Reuse it in both `classifier.py` and `evaluate.py`.
- Remove dead code: `mails.py` duplicates the golden set — delete or fold into `data/golden.yaml`.
- Add `.env.example`; keep `.env` gitignored (already is). Rotate any keys shared in plaintext.

## Phase 1 — Real metrics (the "quality" definition)
- New `metrics.py`. Compute per run: overall accuracy, **per-category precision / recall / F1**,
  **confusion matrix**, and parse-failure rate. Use `scikit-learn` (`classification_report`,
  `confusion_matrix`).
- Define a typed `EvalResult` (pydantic): prompt version, model id, timestamp, all metrics, and
  per-case predictions (for debugging which cases regressed).
- Serialize `EvalResult` to `results/<prompt>__<model>__<ts>.json`.

## Phase 2 — Regression detection (the CORE)
- New `regression.py`. Load committed `baselines/baseline.json` and a fresh `EvalResult`.
- Compute deltas (overall accuracy, each category F1). Flag a **regression** if:
  - overall accuracy drops by more than `--fail-under-delta` (default e.g. 0.03), OR
  - any category F1 drops beyond threshold, OR
  - parse-failure rate increases.
- Produce a `RegressionReport` (pass/fail + human-readable diff table + which case ids flipped).
- CLI exit code: `0` pass, `1` regression — this is what makes CI gate the PR.
- Commands via `cli.py`:
  - `python -m emailclf eval --prompt v2 --model <id>` → run + print metrics + save result
  - `python -m emailclf check --prompt v2 --model <id>` → run + diff vs baseline + exit code
  - `python -m emailclf update-baseline --from <result.json>` → promote a result to baseline
  - `python -m emailclf compare --prompts v1,v2` → side-by-side prompt/model comparison table

## Phase 3 — Slack alerting
- New `alert.py`: post a formatted message to `SLACK_WEBHOOK_URL` (Slack Incoming Webhook) on
  regression — include prompt/model, accuracy delta, and the flipped cases. Graceful no-op +
  warning if the env var is unset (so local runs and tests don't need Slack).
- Wire `check` to call the alerter when a regression is detected.

## Phase 4 — CI/CD pipeline (makes it a "system")
- `.github/workflows/eval.yml`:
  - Triggers: `pull_request` with `paths: [prompts/**, data/**, emailclf/**, baselines/**]`
    (the "whenever a prompt or model changes" trigger).
  - Steps: checkout, setup-python, install, run `python -m emailclf check ...`.
  - On regression: job fails (blocks merge) AND Slack alert fires.
  - Secrets: `HUGGING_FACE_API_KEY`, `SLACK_WEBHOOK_URL` via GitHub repo secrets.
- **Cost/determinism concern**: hitting a live LLM in CI is slow/flaky/costs money. Run the real
  eval only when prompts/data change (small golden set keeps it cheap), and keep the **unit
  tests** (Phase 5) fully mocked so the bulk of CI is free and deterministic. Document this
  tradeoff in the README (shows engineering judgment).

## Phase 5 — Tests + polish (CV hygiene)
- `pytest` unit tests with the **LLM mocked** (monkeypatch the classifier call): cover
  `parse_model_json` edge cases (fenced/prose/garbage), metrics math, and regression
  pass/fail/threshold logic. Fast, no API keys needed.
- `pyproject.toml`: package metadata, pinned deps, `ruff` + `pytest` config. Drop unused
  `langchain[google-genai]`/`langchain-openai` unless provider-agnostic is pursued.
- Expand `data/golden.yaml` to ~30-50 labeled emails including ambiguous + `unknown` cases — a
  regression detector needs enough signal to actually move metrics.
- **README.md** (the centerpiece): one-paragraph problem statement, architecture diagram, a
  "regression caught" screenshot/log, the metrics it reports, how to run locally, and the CI badge.

## Optional stretch (only if targeting strong ML/LLM roles)
- Provider abstraction (`classifier.py` strategy over HF / Groq / Gemini / OpenAI — keys already
  present) so "any model change" is real, enabling model-vs-model regression comparison.
- Trend tracking: append each run to a history file and plot accuracy-over-time.

---

## Critical files
- Modify/move: `main.py`, `evaluate.py`, `schema/promptsSchema.py`, `prompts.py`,
  `tests/ground_truth.yaml`, `requirements.txt`, `.gitignore`.
- Create: `emailclf/metrics.py`, `emailclf/regression.py`, `emailclf/alert.py`,
  `emailclf/cli.py`, `baselines/baseline.json`, `.github/workflows/eval.yml`, `pyproject.toml`,
  `.env.example`, `README.md`, `tests/test_*.py`.
- Delete: `mails.py` (duplicate of golden set).

## Verification (end-to-end demo the README will show)
1. `pip install -e .` then `pytest` → all unit tests pass with **no** API key (mocked).
2. `python -m emailclf eval --prompt v2 --model Qwen/Qwen2.5-7B-Instruct` → prints metrics,
   writes a `results/*.json`.
3. `python -m emailclf update-baseline --from results/<latest>.json` → creates baseline.
4. Introduce a deliberately worse prompt `prompts/v3.yaml`; run
   `python -m emailclf check --prompt v3 ...` → exit code 1, prints a diff table showing the
   accuracy drop + flipped case ids, and (if `SLACK_WEBHOOK_URL` set) posts a Slack alert.
5. Open a PR changing `prompts/v3.yaml` → GitHub Actions `eval.yml` runs, the check fails, merge
   is blocked, Slack alert fires. Screenshot this for the README.
