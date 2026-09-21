# Part 4 — Client handover note

**Audience:** business owner / product owner  
**Subject:** what this movie assistant pilot does, what we stand behind, and how to
verify it

---

## What we commit to

We commit to the following for this pilot catalogue and for users who already have
rating history in that catalogue:

1. **Lookups stay inside the catalogue.** When the assistant names a film, that
   film should appear in the underlying data the tools returned—not invented titles.
2. **Clear refusals when we cannot help.** If the user is unknown, or the film
   title cannot be matched, the system should say it cannot answer rather than
   guess. On our scripted checks, those refusal paths passed in full (20 of 20
   unknown-user cases; 20 of 20 unknown-title cases).
3. **Peer opinion is a group signal, not a personal prediction.** When we summarise
   what similar raters think of a film, expect typical error on the order of about
   **0.7 stars** on a 0.5–5.0 scale (measured as mean absolute error on 240 held-out
   user–film pairs). Useful for context; not a guarantee of what this user will rate.
4. **Personal suggestions are exploratory, not proven better than “popular films.”**
   In offline tests that hide films a user already liked, a simple popularity list
   recovered those films more often than our personalised list (about **53%** of
   users vs about **28%**). We therefore do **not** commit to beating popularity on
   ranking quality in this pilot.
5. **Fixed assistant behaviours we re-check.** On our 20-prompt agent suite, tool
   routing and written answers currently pass **20/20** (including “films like X”
   after seed-genre ranking). Live traffic can still drift; we treat the suite as a
   regression gate, not as proof of every future question.

How we measure quality day to day in the pilot: refusal rate, error or fallback
rate, response time, periodic re-runs of the same offline scripts, and samples of
similarity / explanation asks.

---

## What the system deliberately does not do

- It does **not** cover every film in the market. The pilot catalogue is limited
  (MovieLens-scale data ending around 2014). Many recent or famous titles will be
  refused as unknown.
- It does **not** replace a human curator or a guarantee that the user will enjoy
  every suggestion.
- It does **not** invent plot facts or ratings outside tool results. If evidence is
  missing, it should decline or stay within what was retrieved.
- It does **not** claim superior personalisation over showing popular titles. That
  claim is not supported by our ranking measurements.
- It does **not** serve users with no history as if it knew their taste; those
  cases should be refused or handled without false personalisation.

---

## How you can check our claims yourself

You do not need to trust a slide. With the project and (for the chat agent) an API
key:

Full command list and parameters: [run-eval.md](run-eval.md). Saved agent
transcript: [samples/eval_agent_results.json](samples/eval_agent_results.json).

1. **Ranking and popularity comparison** — `eval_recommend.py` (seed 42). You
   should see personalised Hit@10 below the popularity baseline—the same
   limitation we state above.
2. **Peer opinion error** — `eval_peer.py`. Mean absolute error near **0.7**.
3. **Refusals** — `eval_decline.py`. Unknown users and titles should pass in full.
4. **End-to-end assistant** — `eval_agent.py`. Our run: tools **20/20**; written
   answers **20/20**.
5. **Manual spot check**  
   Ask, for a known user id in the data: a tonight recommendation, a peer question
   on a known title, a made-up title, and “something like [a catalogue film].”
   Confirm refusals where expected and that named films exist in the catalogue.

Saved evaluation outputs from our run are included with the report so you can read
numbers before re-running anything.

---

## When it gets something wrong

| Situation | What you should see | What we do |
|-----------|---------------------|------------|
| Unknown user or title | An explicit decline, not a fabricated answer | Keep refusal rules on; fix catalogue matching if real titles are refused too often |
| Suggestion list feels off-topic for “like film X” | Should be uncommon after seed-genre ranking; still sample in production | Feature-flag similarity mode if live samples fail above threshold; re-check agent suite |
| Peer average far from the user’s later rating | Expected within roughly one star on average | Present peer results as “people like you,” not as a promise |
| Assistant names a film that is not in the data | Unacceptable | Investigate grounding; if recurring above our internal sample threshold, disable the language-model path and fall back to deterministic tools only, or pause the assistant |
| Slow or failing responses | Timeouts or fallback messages | Alert on high error rate or high latency; roll back the language-model path if errors stay elevated |

**In short:** wrong answers should fail **closed** (decline or fallback), not by
inventing catalogue entries. Ranking quality is disclosed as below a popularity
baseline on our current test; we will not sell the opposite story.

---

## Bottom line for the handover

This pilot is suitable as a **catalogue-grounded assistant** for explanation,
lookup, and careful suggestions—with honest limits on coverage and ranking. It is
not suitable yet as a flagship “better than popular” recommender. You can verify
every quantitative claim above by re-running the published evaluation commands.
