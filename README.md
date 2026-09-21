# Movie assistant PoC

Personalised movie assistant over a MovieLens catalogue subset, with evaluation
scripts and written reports (Parts 2–5).

**Start here:** [docs/README.md](docs/README.md)

## Quick start

From the project root:

```bash
uv sync
cp .env.example .env   # set OPENAI_API_KEY

uv run python -m sources.cli --user 1 --query "what should I watch tonight?"
uv run python scripts/eval_recommend.py --n-users 80 --seed 42 --k 10
```

Dataset: `data/ml-latest-small-filtered/` (override with `DATA_DIR` if needed).

## Layout

| Path | Contents |
|------|----------|
| `sources/` | Assistant, agent, tools |
| `scripts/` | Evaluation and dataset verify |
| `docs/` | Parts 2–5, run guides, sample outputs |
| `data/` | MovieLens filtered CSVs |
| `pyproject.toml` / `uv.lock` | Dependencies |
