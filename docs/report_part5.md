# Part 5 — Note on AI use

I used an AI coding assistant throughout this PoC. Below is what I asked it to
own, what it got right, what it got wrong, and what I overrode.

---

## 1. Implementation (LangChain, tools, I/O)

**What I directed:** use a single LangChain orchestrator (`ChatOpenAI` + tool
calling), define a fixed tool belt over the MovieLens catalogue, and keep
input/output grounded (decline unknown users in code; answers only from tool
evidence).

**What the AI wrote:** most of the `sources/` package—catalogue loading, tool
wrappers, recommend / peer / decline paths, the agent loop, CLI, and env wiring
(including switching off Azure-style base URLs in favour of the public OpenAI
API).

**What it got right:** a clear split between deterministic tools and the LLM
orchestrator; refusal before the model when `userId` has no ratings; structured
tool results the agent can cite.

**What it got wrong / what I overrode:** early model id / endpoint confusion
(`gpt-5.4-mini-test`, leftover Azure assumptions) until corrected against a
working public model; I also kept trimming tool surface and prompts so the agent
did not grow into sub-agents or invent film facts outside metadata.

---

## 2. Evaluation design (two metric families)

**What I directed:** define two evaluation layers.

1. **Non-agent (no LLM in the metric path)** — classical recommend / peer /
   refusal checks: hold-out Hit@K and nDCG@K versus a popularity baseline; peer
   mean absolute / RMSE error against a hidden rating; scripted unknown-user and
   unknown-title declines.
2. **Agent** — deterministic checks that the right tools (and decline flags)
   fired, plus an **LLM-as-judge** on groundedness and task fit of the written
   answer.

**What the AI wrote:** the `scripts/eval_*.py` suite and the first draft of the
Part 2 write-up explaining those numbers.

**What it got right:** reproducible non-agent scripts; a fixed 20-case agent
battery with separate tool vs judge scores; saving a full JSON transcript.

**What it got wrong / what I overrode:** the assistant initially treated Hit@10
vs popularity as a stronger product verdict than it deserves (many hold-outs are
popular titles). I kept the metric as an honest ranking sanity check and refused
to let Part 2/3 over-claim “personalisation wins.” I also pushed back when prose
leaned on offline jargon instead of product risk. When agent suite misses showed
up on “like X” / over-explained answers, I directed seed-genre ranking and stricter
grounding prompts rather than accepting a permanent 19/20 narrative.

---

## 3. Part 3 — engineering note (ideas → AI prose)

**What I supplied:** bullet problems and directions—do not full-release as a
“smarter than popular” default; pilot only; next work should be tracing
(e.g. Langfuse), guardrails, FAQ-oriented cache, and assistant fixes (especially
“like X”); production = alerts, 100× failure modes, rollback.

**What the AI wrote:** the structured Part 3 markdown from those bullets.

**What it got right:** concrete monitor thresholds, cache TTLs, and a coherent
“next change” section once I specified observability + features.

**What I overrode:** section 3.1 reasons rewritten away from offline-metric
language into product trust / expectation language; removed catalogue-year
tangents; moved guardrails and FAQ cache into 3.2 instead of burying cache only
in 3.3; tone pass to cut slang and scare-quotes.

---

## 4. Part 4 — client handover (commitments → AI prose)

**What I supplied:** the commitments and limits to state to a business owner—
what quality we stand behind, what the system deliberately does not do, how the
client re-runs evals themselves, and what happens when answers are wrong—plus
the real numbers from Part 2.

**What the AI wrote:** the one-page handover note in plain language.

**What it got right:** mapping each claim to a runnable check; fail-closed story
(refuse / fallback rather than invent titles).

**What I overrode:** wording so we explicitly **do not** commit to beating
popularity on ranking; pointed “how to check” at `docs/run-eval.md` and the saved
agent JSON after the docs reorganisation; kept jargon out of the client-facing
page.

---

## Short summary

| Area | AI role | My role |
|------|---------|---------|
| LangChain agent + tools | Wrote most code | Architecture, API/model corrections, grounding rules |
| Non-agent + agent metrics | Implemented suite + first explanations | Metric choice, honest reading of Hit@K vs popular |
| Part 3 | Turned issue/idea lists into prose | Product framing, what goes in 3.2 vs 3.3, tone |
| Part 4 | Turned commitment bullets into client prose | What we will and will not promise |

I treat the assistant as a fast implementer and drafter. Claims, ship/no-ship
judgement, and anything that goes to the client stay owned by me.
