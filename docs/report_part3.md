# Part 3 — Engineering note

This note is based on the evaluation results in Part 2. Where cost or traffic is
discussed, assumptions are stated explicitly. The reasoning matters more than the
precise figures.

---

## 1. Would we release this to the client’s users?

**Not as a general-purpose personalised recommender, and not with a claim that it
outperforms simple popularity-based suggestions.** A limited pilot with clear
scope is acceptable; a broad release is not.

### Reasons against a full release

- Personalised suggestions are not yet clearly more useful than simply pointing
  users at well-known titles. Shipping this as the default “smart for you”
  experience would set an expectation we cannot reliably meet on ranking quality.
- The assistant is still tuned for a narrow, supervised setting (known users,
  known catalogue behaviour, staff who understand its limits). Opening it to
  everyone before observability, guardrails, and FAQ caching are in place invites
  support load when live traffic drifts from the fixed eval suite.
- Catalogue coverage and cold-start users remain limited; refusals will be common
  and must stay clearly labelled.

### Reasons a limited pilot can still be justified

- For signed-in users with history, the assistant can explain taste in plain
  language and surface peer opinion as context—useful even when it is not sold as
  a perfect score predictor.
- When it cannot identify the user or the film, it tends to refuse instead of
  inventing an answer. That behaviour is worth keeping in front of real users in
  a small group.
- On the fixed agent suite, tools and written answers now pass end-to-end
  (including seed-similar “like X” after ranking/prompt fixes). Remaining work is
  operational hardening more than basic task coverage.

### Acceptable release shape

- Surface: a catalogue assistant for explanation and lookup, with suggestions
  framed as ideas from this catalogue—not as a guarantee of better picks than
  popular titles.
- Audience: internal or invited beta users first, with clear copy about limits.
- Gate: expand only after tracing and guardrails are live, and product messaging
  still matches what ranking metrics actually support.

**Decision:** no full production release today; yes to a constrained, accurately
labelled pilot.

---

## 2. The next change we would make

**Add observability, harden the assistant with guardrails and an FAQ-oriented
cache, then ship a short list of capability fixes—guided by what the traces show.**

Today we can run offline scripts and inspect chats by hand. We cannot see at scale
which tools fired, where answers drifted, or which repeated questions burn language
model budget. Without tracing, cache, and clearer safety rails, further feature
work stays guesswork.

### What we would add

**A. Observability (for example Langfuse, or an equivalent trace store)**

- One trace per user turn: prompt version, model, tool calls and arguments, tool
  latency, final answer, decline flag, token usage, and error class.
- Dashboards for p95 latency, tool-loop depth, refusal rate, and cost per turn.
- Ability to slice failing similarity turns and compare prompt versions side by side.

**B. Guardrails (policy before and after the model)**

- **Input:** block or sanitize empty / oversized prompts; require a resolved user
  id before personalised tools; reject prompts that ask to invent titles outside
  the catalogue.
- **Tool boundary:** only allow the existing tool belt; no free-form browsing or
  arbitrary code paths.
- **Output:** refuse if the final answer cites a film id or title that never
  appeared in tool results; force decline when resolve_movie returns not found;
  optional second-pass check for fabricated star ratings.
- **Feature flags:** ability to disable similarity mode or the language-model path
  without redeploying the whole service.

**C. Cache aimed at building an FAQ layer**

- Cache **tool evidence** (not long-lived final prose): taste summary and neighbour
  list per user (**24h**, invalidate on new rating); resolved title payload per film
  (**7d**); peer mean per (user, film) (**24h**).
- From traces, cluster repeated questions (for example “what should I watch?”,
  “people like me on Pulp Fiction”, common “like X” seeds). Promote stable,
  reviewed answers—or templated answers filled from cached tool payloads—into a
  **FAQ / playbook** served before calling the language model when the match is
  high.
- Goal: cut cost and latency on the head of the query distribution, while keeping
  the model for long-tail and personalised asks.

**D. Assistant capability improvements**

1. **Stronger title resolution** — typos, alternate titles, and clearer “not in
   catalogue” refusals across messy real-world strings.
2. **Short session memory within a chat** — follow-ups like “more like the second
   one.”
3. **Optional user feedback** (useful / not useful) into the same tracing review
   queue.

*(Seed-faithful “like film X” ranking and prompt rules are already in the current
codebase and pass the fixed agent suite; keep monitoring them in production
samples.)*

### Expected improvement

- Faster diagnosis of bad answers (open the trace; see tools and timing).
- Fewer ungrounded or policy-breaking replies in front of users (guardrails).
- Lower average cost and latency on repeated questions via FAQ cache hits.
- Safer iteration on prompts and tools, plus better follow-ups and title matching.

### Cost and trade-offs

- **Cost:** roughly **one to two engineering weeks** for tracing, guardrail hooks,
  cache + first FAQ promotions, and stronger title resolution. Session memory and
  feedback can follow. Langfuse (or equivalent) is modest at pilot volume versus
  language-model spend.
- **Trade-off:** traces and FAQ entries contain user-related content—retention and
  access policy required. Over-strict output guards may over-refuse borderline
  valid answers; tune on sampled traces. Stale FAQ entries must expire or be
  re-validated when catalogue or prompts change. Session memory can confuse if it
  keeps stale context—keep it short and resettable.

### Evidence that would show the change worked

1. **Tracing:** ≥95% of pilot turns appear in the trace store within one minute,
   with tools and latencies populated.
2. **Guardrails:** on a regression pack of invent-title / unknown-user / unknown-
   title prompts, refuse or block rate stays at **100%**; false declines on valid
   catalogue asks stay rare (target under **2%** in a fixed valid set).
3. **FAQ cache:** within two weeks of pilot traffic, at least **20–30%** of turns
   hit a cached tool payload or FAQ template (exact share depends on query mix);
   those hits show lower p95 latency than full tool-loop turns.
4. **Regression:** the fixed agent suite stays at **20/20** (or no drop below
   19/20 across judge noise) after each rollout; sampled live “like X” and explain
   questions stay on-topic.
5. **Cost envelope:** average tokens per turn and p95 latency stay inside an agreed
   band for two weeks after rollout (for example p95 still under about eight
   seconds at pilot load).

---

## 3. What changes between this prototype and production

### Assumptions

- Pilot traffic on the order of **1,000–10,000 assistant queries per day**, not
  full storefront request volume.
- One language-model stack per turn (tool loop of at most about eight rounds),
  model class similar to the current configuration.
- The prototype catalogue is bounded (thousands of films, hundreds of users).
  Production would replace MovieLens with the client catalogue and real histories.

### Monitoring and thresholds

| Signal | Purpose | Initial alert threshold |
|--------|---------|-------------------------|
| Refusal rate (unknown user, unknown title, explicit decline) | Spike may indicate identity or catalogue sync issues; collapse may indicate fabricated answers | Outside **5–25%** of turns over a week → investigate (band recalibrated after the first pilot week) |
| Share of turns with six or more tool calls | Cost and latency | **>10%** → shorten prompts or raise FAQ / tool-cache hit rate |
| Language-model error / fallback rate | Silent quality drop | **>2%** of turns → page on-call; **>5%** → disable the language-model path and serve fallback / FAQ only |
| p95 end-to-end latency | User experience | **>8 seconds** for 15 minutes → scale capacity or shorten the tool loop |
| Sampled similarity-answer failures | Product risk on “like X” | Weekly sample of 50 similarity queries; **>10%** fail → turn similarity mode off behind a feature flag |
| FAQ / cache hit rate | Confirms the section-2 cache work pays off in production | Sustained drop below the pilot baseline (for example under **15%** after it had been higher) → investigate invalidation or clustering |

These thresholds are starting points and should be recalibrated from the first week
of live traffic percentiles. Caching and FAQ construction themselves are planned
in section 2; production mainly operates and alerts on them.

### What fails first at roughly 100× users

1. **Language-model spend and rate limits** — each turn may involve multiple model
   calls; query volume hits quota before in-memory catalogue arithmetic does.
2. **Neighbour-scan latency** — similar-user search scales poorly with the number
   of users unless neighbours are precomputed or indexed.
3. **Per-request catalogue scans** for hybrid candidates — acceptable at prototype
   scale; at much larger catalogues and user counts, candidate generation needs
   indexing.

In-memory tables at MovieLens size are unlikely to be the first failure mode.
Language-model cost and repeated full scans are.

### Rollback criteria

Roll back if any of the following occurs:

- Language-model / fallback error rate above **5%** for 30 minutes.
- p95 latency above **12 seconds** with no rapid mitigation.
- Spot checks or judge samples showing more than **15%** of answers citing films
  not present in tool metadata.
- Continued marketing of superior personalisation while weekly offline Hit@10
  remains at least **0.15** below the popularity baseline.

Rollback means: disable the language-model orchestrator behind a feature flag,
serve deterministic recommend / peer / decline paths only (or hide the assistant),
and keep refusal gates enabled.

---

## Summary

Treat this prototype as a **grounded lookup and explanation** pilot, not as a
proven ranking upgrade over popularity. Seed-similar recommendations now pass the
fixed agent suite; the next engineering priority is **tracing, guardrails, and an
FAQ-oriented cache**, plus title-resolution and session follow-ups. Production then
operates those controls at scale: alerts, rollback, and honest product claims.
