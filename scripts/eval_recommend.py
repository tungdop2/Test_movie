#!/usr/bin/env python3
"""Recommend hold-out eval (no LLM): Hit@K / nDCG@K vs popular baseline.

  uv run python scripts/eval_recommend.py
  uv run python scripts/eval_recommend.py --n-users 80 --seed 42 --k 10
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eval_lib import (
    hit_at_k,
    load_catalog,
    ndcg_at_k,
    popular_baseline,
    print_report,
    sample_users,
    temporarily_mask_user_ratings,
)
from sources.recommend import recommend


def eval_recommend(
    catalog,
    user_ids: list[int],
    *,
    k: int,
    holdout_liked: int,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed + 1)
    hits_model: list[float] = []
    hits_pop: list[float] = []
    ndcgs_model: list[float] = []
    ndcgs_pop: list[float] = []
    used = 0

    for user_id in user_ids:
        liked = [
            mid
            for mid, rating in catalog.ratings_by_user[user_id].items()
            if rating >= 4.0 and mid in catalog.movies
        ]
        if len(liked) < holdout_liked + 5:
            continue
        holdout = set(rng.sample(liked, holdout_liked))
        train_seen = set(catalog.ratings_by_user[user_id]) - holdout

        with temporarily_mask_user_ratings(catalog, user_id, holdout):
            result = recommend(catalog, user_id, k=k)
            model_ids = [r.movie.movie_id for r in result.recommendations]
            pop_ids = popular_baseline(catalog, exclude=train_seen, k=k)

        hits_model.append(hit_at_k(model_ids, holdout, k))
        hits_pop.append(hit_at_k(pop_ids, holdout, k))
        ndcgs_model.append(ndcg_at_k(model_ids, holdout, k))
        ndcgs_pop.append(ndcg_at_k(pop_ids, holdout, k))
        used += 1

    def avg(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 4) if xs else None

    return {
        "n_users_evaluated": used,
        "holdout_liked_per_user": holdout_liked,
        "k": k,
        "model": {"hit_at_k": avg(hits_model), "ndcg_at_k": avg(ndcgs_model)},
        "popular_baseline": {"hit_at_k": avg(hits_pop), "ndcg_at_k": avg(ndcgs_pop)},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval recommend (no LLM)")
    parser.add_argument("--n-users", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--holdout-liked", type=int, default=5)
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args(argv)

    catalog = load_catalog(args.data_dir)
    users = sample_users(catalog, args.n_users, args.seed)
    report = {
        "eval": "recommend",
        "llm_used": False,
        "config": {
            "n_users_sampled": len(users),
            "seed": args.seed,
            "k": args.k,
            "holdout_liked": args.holdout_liked,
        },
        "results": eval_recommend(
            catalog,
            users,
            k=args.k,
            holdout_liked=args.holdout_liked,
            seed=args.seed,
        ),
    }
    print_report(report, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
