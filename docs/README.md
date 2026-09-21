# Documentation

Table of contents for this movie assistant PoC. Code lives under `sources/` and
`scripts/`; written deliverables and how-to guides live here.

---

## How to run

| Doc | Contents |
|-----|----------|
| [run-system.md](run-system.md) | Setup, environment variables, CLI examples |
| [run-eval.md](run-eval.md) | Evaluation commands, parameters, what each script prints |

## Reports

| Part | English | Vietnamese |
|------|---------|------------|
| Part 2 — Evaluation | [report_part2.md](report_part2.md) | [report_part2.vi.md](report_part2.vi.md) |
| Part 3 — Engineering note | [report_part3.md](report_part3.md) | [report_part3.vi.md](report_part3.vi.md) |
| Part 4 — Client handover | [report_part4.md](report_part4.md) | [report_part4.vi.md](report_part4.vi.md) |
| Part 5 — Note on AI use | [report_part5.md](report_part5.md) | [report_part5.vi.md](report_part5.vi.md) |

How to re-run the measurements is documented in [run-eval.md](run-eval.md), not
inside Part 2.

## Sample outputs

| Doc / file | Contents |
|------------|----------|
| [samples/README.md](samples/README.md) | How to read the saved agent evaluation JSON |
| [samples/eval_agent_results.json](samples/eval_agent_results.json) | Full agent suite run (20 cases; tools 20/20, overall 20/20) |

## Related paths

| Path | Role |
|------|------|
| [`../README.md`](../README.md) | Project overview |
| [`../sources/`](../sources/) | Assistant, agent, tools, catalogue |
| [`../scripts/`](../scripts/) | `eval_*.py`, `verify_dataset.py` |
| [`../data/ml-latest-small-filtered/`](../data/ml-latest-small-filtered/) | MovieLens subset |
| [`../.env.example`](../.env.example) | API key / model template |
