#!/usr/bin/env python3
"""Peer-opinion eval (no LLM): MAE / RMSE of peer mean vs user's rating.

  uv run python scripts/eval_peer.py
  uv run python scripts/eval_peer.py --n-users 80 --seed 42 --pairs-per-user 3
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eval_lib import load_catalog, print_report, sample_users, temporarily_mask_user_ratings
from sources.peer import peer_opinion
from sources.tools import ResolvedMovie


def eval_peer(
    catalog,
    user_ids: list[int],
    *,
    pairs_per_user: int,
    seed: int,
    min_raters: int = 20,
) -> dict[str, Any]:
    rng = random.Random(seed + 2)
    abs_errors: list[float] = []
    ok_pairs = 0
    skipped = 0

    for user_id in user_ids:
        candidates = [
            mid
            for mid, _rating in catalog.ratings_by_user[user_id].items()
            if mid in catalog.movies and len(catalog.ratings_by_movie.get(mid, {})) >= min_raters
        ]
        if not candidates:
            continue
        sample = (
            candidates
            if len(candidates) <= pairs_per_user
            else rng.sample(candidates, pairs_per_user)
        )
        for movie_id in sample:
            true_rating = catalog.ratings_by_user[user_id][movie_id]
            movie = catalog.movies[movie_id]
            resolved = ResolvedMovie(movie=movie, score=1.0, matched_as="exact")
            with temporarily_mask_user_ratings(catalog, user_id, {movie_id}):
                result = peer_opinion(catalog, user_id, resolved, neighbor_k=40)
            if not result.ok or result.mean is None:
                skipped += 1
                continue
            abs_errors.append(abs(result.mean - true_rating))
            ok_pairs += 1

    mae = round(sum(abs_errors) / len(abs_errors), 4) if abs_errors else None
    rmse = (
        round(math.sqrt(sum(e * e for e in abs_errors) / len(abs_errors)), 4)
        if abs_errors
        else None
    )
    return {
        "n_pairs": ok_pairs,
        "n_skipped": skipped,
        "mae": mae,
        "rmse": rmse,
        "note": "Peer-similar mean vs user's own rating on the same movie.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval peer opinion (no LLM)")
    parser.add_argument("--n-users", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pairs-per-user", type=int, default=3)
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args(argv)

    catalog = load_catalog(args.data_dir)
    users = sample_users(catalog, args.n_users, args.seed)
    report = {
        "eval": "peer_opinion",
        "llm_used": False,
        "config": {
            "n_users_sampled": len(users),
            "seed": args.seed,
            "pairs_per_user": args.pairs_per_user,
        },
        "results": eval_peer(
            catalog,
            users,
            pairs_per_user=args.pairs_per_user,
            seed=args.seed,
        ),
    }
    print_report(report, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
