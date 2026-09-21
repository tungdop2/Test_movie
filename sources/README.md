# Movie assistant

One **orchestrator agent** (LangChain `ChatOpenAI` + tools) chooses which **tools** to call. No sub-agents.

Full setup and CLI docs: [`docs/run-system.md`](../docs/run-system.md).  
Evaluation how-to: [`docs/run-eval.md`](../docs/run-eval.md).  
Reports and samples: [`docs/README.md`](../docs/README.md).

Run all commands from the **project root**.

## Setup

```bash
uv sync
cp .env.example .env   # set OPENAI_API_KEY
```

## Run

```bash
uv run python -m sources.cli --user 1 --query "what should I watch tonight?"
uv run python -m sources.cli --user 1 --query "what do people with taste like mine think of Pulp Fiction?"
uv run python -m sources.cli --user 1 --query "Pulp Fiction or Fight Club — which fits my taste better?"
uv run python -m sources.cli --user 99999 --query "what should I watch tonight?"
```

## Flow

1. `DeclineGate` — unknown `userId` (no ratings) → refuse (code, no LLM)
2. Orchestrator agent — LangChain tool-calling loop over grounded lookups
3. Final natural-language answer from tool evidence only

## Tools

| Tool | Role |
|------|------|
| `get_taste_summary` | Gu từ ratings |
| `resolve_movie` | Title → catalogue / not found |
| `find_similar_users` | Neighbors (optional: only raters of a movie) |
| `get_movie_ratings_summary` | Aggregate ratings (all or similar users) |
| `find_candidate_movies` | Unseen candidates |
| `collaborative_recommend` | Collab + genre fallback |
| `compare_movies_for_user` | Multi-lookup A vs B |

## Env

| Variable | Required | Meaning |
|----------|----------|---------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `OPENAI_MODEL` | No | Default `openai:gpt-5.4-mini` |
| `OPENAI_BASE_URL` | No | Optional custom endpoint (leave empty for api.openai.com) |
| `DATA_DIR` | No | Override; default `data/ml-latest-small-filtered` |
