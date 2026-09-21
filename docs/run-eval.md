# Running evaluations

How to re-run every Part 2 measurement, what each parameter means, and what you
should expect on stdout. Interpretation of the numbers lives in
[report_part2.md](report_part2.md); this page is only about **running** the scripts.

All commands are from the **project root**. Dataset defaults to
`data/ml-latest-small-filtered`.

| Script | Needs LLM? | Typical role |
|--------|------------|--------------|
| `scripts/eval_recommend.py` | No | Hold-out ranking vs popularity |
| `scripts/eval_peer.py` | No | Peer-mean vs hidden rating |
| `scripts/eval_decline.py` | No | Unknown user / title refusals |
| `scripts/eval_agent.py` | Yes | 20 fixed prompts (tools + judge) |

---

## Shared parameters

| Parameter | Used by | Meaning |
|-----------|---------|---------|
| `--data-dir PATH` | all | Override dataset directory (default: project MovieLens subset) |
| `--out PATH` | all | Optional path to write the full JSON report (also printed to stdout) |
| `--seed N` | recommend, peer | RNG seed for sampling users / hold-outs / pairs. Same seed → same sample. Default **42**. |
| `--n-users N` | recommend, peer | How many users to sample (eligible users need enough ratings). Default **80**. |

---

## 1. Recommendation ranking

```bash
uv run python scripts/eval_recommend.py --n-users 80 --seed 42 --k 10
```

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `--n-users` | `80` | Users sampled (each must have enough liked films) |
| `--seed` | `42` | Deterministic sample + hold-out draws |
| `--k` | `10` | Length of the recommendation list (Hit@K / nDCG@K) |
| `--holdout-liked` | `5` | How many liked films (rating ≥ 4.0) to hide per user |
| `--data-dir` | project data | Catalogue root |
| `--out` | none | Write JSON report to this path |

**What it prints:** `n_users_evaluated`, Hit@K / nDCG@K for the model and for the
popularity baseline.

**Reference numbers (seed 42, n-users 80, k 10):** model Hit@10 ≈ **0.275**, popular
Hit@10 ≈ **0.525**.

---

## 2. Peer opinion

```bash
uv run python scripts/eval_peer.py --n-users 80 --seed 42 --pairs-per-user 3
```

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `--n-users` | `80` | Users sampled |
| `--seed` | `42` | Deterministic sample / pair selection |
| `--pairs-per-user` | `3` | Max films per user → up to `n-users × pairs-per-user` pairs |
| `--data-dir` | project data | Catalogue root |
| `--out` | none | Write JSON report |

**What it prints:** MAE, RMSE, number of pairs used / skipped.

**Reference numbers (seed 42, 240 pairs):** MAE ≈ **0.74**, RMSE ≈ **0.94**, skipped
**0**.

---

## 3. Decline / refusal

```bash
uv run python scripts/eval_decline.py
```

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `--data-dir` | project data | Catalogue root |
| `--out` | none | Write JSON report |

No sampling knobs: fixed batteries of unknown users, unknown titles, and positive
controls.

**Reference:** unknown user **20/20** refused; unknown title **20/20** refused;
real user / real title accepted.

---

## 4. Agent end-to-end

Requires `OPENAI_API_KEY` (see [run-system.md](run-system.md)).

```bash
uv run python scripts/eval_agent.py --out docs/samples/eval_agent_results.json
```

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `--out` | none | Where to save the detailed per-case JSON (recommended) |
| `--limit N` | all 20 | Run only the first N cases (smoke test) |
| `--ids IDS` | all | Comma-separated case ids, e.g. `L01,R01` |
| `--data-dir` | project data | Catalogue root |

**What it prints / saves:** summary pass rates plus, in the JSON, each case’s
expected block, tool checks, judge scores, and the agent’s message / metadata.

**Reference run:** tools **20/20**, judge **20/20**, overall **20/20**.
Saved copy and field-by-field explanation:
[samples/README.md](samples/README.md),
[samples/eval_agent_results.json](samples/eval_agent_results.json).

Judge scores can vary slightly across runs; tool checks are deterministic given the
same tool outputs.

---

## Suggested order

1. `eval_recommend.py`, `eval_peer.py`, `eval_decline.py` — no API key, fast.
2. `eval_agent.py` — needs key; slower; write `--out` under `docs/samples/` if you
   want to refresh the checked-in sample.
