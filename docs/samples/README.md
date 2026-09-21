# Sample outputs

Saved artefacts so a reader can inspect behaviour **before** re-running anything.
An OpenAI API key is required only if you regenerate the agent suite.

---

## Agent evaluation JSON

**File:** [eval_agent_results.json](eval_agent_results.json)

Produced by:

```bash
uv run python scripts/eval_agent.py --out docs/samples/eval_agent_results.json
```

### Top-level fields

| Field | Meaning in this file |
|-------|----------------------|
| `eval` | `"agent"` |
| `llm_used` | `true` — orchestrator + judge both call the API |
| `model` | Chat model id used for the run (e.g. `gpt-5.4-mini`) |
| `n_cases` | Number of fixed prompts (20) |
| `n_passed` | Cases where **both** tool checks and output judge passed |
| `pass_rate` | `n_passed / n_cases` → **1.0** (20/20) |
| `tool_pass_rate` | Share of cases with deterministic tool checks OK → **1.0** |
| `judge_pass_rate` | Share of cases the LLM judge accepted → **1.0** |
| `results` | Array of per-case objects |

### Per-case object

| Block | Meaning |
|-------|---------|
| `id` | Case id (`R01` recommend, `P…` peer, `L…` like-X, `D…` decline, etc.) |
| `passed` | Overall: tools **and** judge both passed |
| `expected` | Rubric: decline flag, required tools, whether recommendations / peer / movies must appear, judge rubric text |
| `tool_eval` | Deterministic checks (`declined_ok`, `require_tools`, `recommendations`, …), `tools_used`, `failures` |
| `output_judge` | `grounded_score`, `task_fit_score`, `rationale`, `passed` |
| `actual` | What the agent returned: `declined`, `tools`, `message`, `metadata` (taste summary, movies, peer payloads, …) |

### How to read the headline result

- **Tools 20/20:** routing and refusals matched the suite; expected film evidence
  showed up in metadata when required.
- **Overall 20/20:** including **L01** (“recommend something like Toy Story”). Open
  that case to see seed-similar picks (e.g. Monsters, Inc., Toy Story 2, Shrek)
  with genre-overlap reasons in tool metadata. Earlier runs failed L01 before
  seed-genre ranking and prompt rules were tightened.

### Regenerating

Overwrite this file with the command above after changing prompts, tools, or the
model. Commit a fresh copy if the submission should show an updated transcript.
