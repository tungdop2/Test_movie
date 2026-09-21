# Part 2 — Evaluation

This section walks through each check in order: what question it answers, how the
procedure works step by step, what the numbers mean, and what we still cannot
claim. Ranking, peer scores, and refusal rules use **no language model**, so the
same command yields the same figures. The agent suite does use a language model:
we first check tools and metadata deterministically, then a separate judge model
scores the written reply.

---

## 1. Recommendation ranking

Commands and parameters: [run-eval.md](run-eval.md#1-recommendation-ranking).

### Question we are asking

If we temporarily hide films a user already liked, does our recommender put any of
those films back into its top 10—and how does that compare with simply listing
popular films they have not rated yet?

### Procedure (step by step)

1. Sample **80** users who have at least **30** ratings (`seed=42` so the sample is
   fixed across runs).
2. For each user, collect films they rated **4.0 or higher** (treated as liked).
3. Randomly hold out **5** of those liked films. While the test runs, those ratings
   are removed from that user’s history (and from the per-film rating maps), so the
   recommender cannot “see” them.
4. Call our hybrid `recommend()` for **10** suggestions from the remaining history.
5. Build a **popularity baseline** for the same user: score every other catalogue
   film by average rating plus a term that grows with how many people rated it;
   exclude films already in the user’s training history; take the top 10.
6. Score both lists against the five hidden films:
   - **Hit@10** = 1 if at least one hidden film appears in the top 10, else 0.
     Average across users.
   - **nDCG@10** = rewards putting hidden films **higher** in the list, not only
     somewhere in the ten. Also averaged across users.

### Results (80 users, seed 42)

| Method | Hit@10 | nDCG@10 | Plain reading |
|--------|--------|---------|---------------|
| Our recommender | **0.275** | 0.062 | About **28%** of users get at least one hidden favourite in the top 10 |
| Popularity baseline | **0.525** | 0.145 | About **53%** — popularity recovers more of those hidden likes |

Other seeds show the same pattern (model Hit@10 roughly 0.22–0.29; popularity stays
ahead).

### How to read this

- The recommender sometimes recovers personalised likes; it is not empty noise.
- On this protocol it still loses to “suggest well-known films the user has not
  rated.” Many held-out likes are themselves popular titles, so popularity has an
  easy path. The fair conclusion is: **do not claim personalisation already beats
  an obvious popular list.**
- This test does **not** measure whether a user would enjoy tonight’s chat reply,
  how the answer is phrased, or users with very thin history (under 30 ratings).

---

## 2. Peer opinion (“people like me”)

Commands and parameters: [run-eval.md](run-eval.md#2-peer-opinion).

### Question we are asking

For “what do people with taste like mine think of this film?”, can we find similar
users, aggregate their ratings on a target film, and land near the user’s own
hidden rating?

### Procedure (step by step)

1. Use the same style of user sample (**80** users, `seed=42`).
2. For each user, pick up to **3** films that enough other people have rated → up to
   **240** user–film pairs.
3. Hide that user’s own rating for the film.
4. Find users with similar rating patterns, keep those who rated the film, and take
   their **mean** rating.
5. Compare that mean to the hidden true rating:
   - **MAE** (mean absolute error): average absolute difference in stars.
   - **RMSE** (root mean squared error): same idea, but larger misses weigh more.

### Results (240 pairs, seed 42)

| Metric | Value | Plain reading |
|--------|-------|---------------|
| MAE | **0.74** | Off by about **0.7 stars** on average (scale 0.5–5.0) |
| RMSE | **0.94** | Occasional larger misses pull this up |
| Skipped pairs | **0** | Every pair produced a numeric peer mean |

### How to read this

- The multi-step path (similar users → aggregate) is reliable on this sample: no
  silent empty results.
- About **0.7 stars** of typical error is usable as a **group signal**—“people like
  you often land around here”—not as a promise of one person’s exact score. Some
  gap is genuine disagreement among “similar” people.
- This test does **not** grade how clearly the assistant explains that number in
  natural language (that is covered in the agent suite below).

---

## 3. Decline / refusal

Commands and parameters: [run-eval.md](run-eval.md#3-decline--refusal).

### Question we are asking

When the catalogue or user history cannot support an answer, does the system
refuse instead of inventing films, users, or ratings—and does it still answer when
the inputs are valid?

### Procedure (step by step)

1. **Unknown users:** 20 fake user ids with no ratings → must decline.
2. **Unknown titles:** 20 fake or impossible titles → must decline.
3. **Positive controls:** a real user id and a real catalogue title (“Pulp Fiction”)
   → must **not** decline.

### Results

| Check | Result | N |
|-------|--------|---|
| Unknown user refused | **100%** | 20 |
| Unknown title refused | **100%** | 20 |
| Real user accepted | yes | 1 |
| Real title accepted | yes | 1 |

### How to read this

On this battery, missing history and missing catalogue titles are caught, and the
positive controls are not blocked by mistake. It does **not** prove every messy
real-world title string (typos, alternate names) will resolve cleanly in production.

---

## 4. Agent end-to-end (20 fixed questions)

Commands and parameters: [run-eval.md](run-eval.md#4-agent-end-to-end).
Saved sample JSON and field guide: [samples/README.md](samples/README.md).

### Question we are asking

On a fixed set of realistic prompts, does the orchestrator call the right tools,
attach the right catalogue evidence, refuse when it should—and is the written
answer grounded and on-task?

### Procedure (step by step)

1. Run **20** fixed prompts covering: personalised recommend, peer opinion,
   “something like film X”, compare two films, unknown user, unknown title, and a
   few broader multi-lookup asks.
2. For each case, score two layers:
   - **Tools (deterministic):** correct decline flag; required tools present; when
     relevant, expected film evidence appears in metadata (recommendations, resolved
     titles, peer payload).
   - **Output (LLM judge):** given that evidence, is the prose grounded (no invented
     titles or numbers), and does it answer or refuse as the task requires?
3. A case **passes overall** only if both layers pass.

### Results (one full run)

| Layer | Pass rate | Notes |
|-------|-----------|-------|
| Tools | **20 / 20 (1.00)** | Routing, refusals, expected movies in metadata |
| Output judge | **20 / 20 (1.00)** | Groundedness and task fit |
| Overall (both must pass) | **20 / 20 (1.00)** | — |

Earlier runs missed **L01** (“recommend something like Toy Story”) because seed
similarity was drowned by general taste / popularity. After tightening
`like_movie_id` ranking (require genre overlap with the seed) and the agent prompt,
L01 returns family/animation neighbours (e.g. Monsters, Inc., Toy Story 2, Shrek)
and the judge passes. Saved transcript: [samples/eval_agent_results.json](samples/eval_agent_results.json).

### How to read this

- Tool choice, scripted refusals, and written answers all pass on this fixed suite,
  including similarity and “why might I like X” explanations.
- This suite does **not** replace the Hit@10 ranking comparison above. Judge scores
  can still vary slightly across runs because the judge itself is a language model.

---

## Bottom line

| Capability | Concrete takeaway |
|------------|-------------------|
| Recommend vs popularity | Runs and returns lists, but **loses** to popularity on hold-out Hit@10 (~28% vs ~53%) |
| Peer multi-lookup | Reliable aggregation; ~**0.7** star MAE as a group signal |
| Scripted refusals | **Pass** on unknown user / unknown title batteries |
| Agent tools | **Pass** (20/20) |
| Agent written answers | **Pass** (20/20) on the fixed suite after seed-similarity fix |

We can defend grounded catalogue lookups, measurable peer aggregation, reliable
scripted refusals, correct tool use, and on-suite written answers including
seed-similar recommendations. We should **not** claim better ranking than
popularity, live user satisfaction, or perfection on every unseen prompt shape.
