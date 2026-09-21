# Running the system

Instructions to install dependencies, configure the API key, and chat with the
movie assistant from the command line.

---

## Prerequisites

- Python 3.12+ (project uses `uv`)
- An OpenAI API key (public API; not Azure)
- Dataset under `data/ml-latest-small-filtered/`

From the **project root**:

```bash
uv sync
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
```

Optional dataset check:

```bash
uv run python scripts/verify_dataset.py
```

---

## Environment variables

| Variable | Required | Default | Meaning |
|----------|----------|---------|---------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `OPENAI_MODEL` | No | `openai:gpt-5.4-mini` | Chat model id (LangChain-style `openai:…` prefix is fine) |
| `OPENAI_BASE_URL` | No | empty | Custom base URL; leave empty for `api.openai.com` |
| `DATA_DIR` | No | `data/ml-latest-small-filtered` | Override catalogue / ratings directory |

Without `OPENAI_API_KEY`, the orchestrator agent will refuse to start with a clear
error. Deterministic evaluation scripts (recommend / peer / decline) do **not** need
a key; the agent evaluation does.

---

## CLI

```bash
uv run python -m sources.cli --user <userId> --query "<natural language>"
```

| Flag | Meaning |
|------|---------|
| `--user` | Catalogue `userId` (must have ratings for personalised answers) |
| `--query` | User question in English or Vietnamese |

### Examples

```bash
# Personalised suggestions
uv run python -m sources.cli --user 1 --query "what should I watch tonight?"

# Peer opinion
uv run python -m sources.cli --user 1 --query "what do people with taste like mine think of Pulp Fiction?"

# Compare two titles
uv run python -m sources.cli --user 1 --query "Pulp Fiction or Fight Club — which fits my taste better?"

# Something like a named film
uv run python -m sources.cli --user 1 --query "recommend something like Toy Story"

# Expected decline (unknown user)
uv run python -m sources.cli --user 99999 --query "what should I watch tonight?"
```

---

## Runtime flow (short)

1. **DeclineGate** — unknown `userId` (no ratings) → refuse in code, no LLM call.
2. **Orchestrator agent** — LangChain tool-calling loop over grounded catalogue tools.
3. **Final answer** — natural language from tool evidence only (system prompt in
   `sources/agent.py`).

More detail on tools: see the table in `sources/README.md`.
