"""Shared helpers for deterministic eval scripts (no LLM)."""

from __future__ import annotations

import json
import math
import random
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sources.catalog import Catalog


def load_catalog(data_dir: str | None = None) -> Catalog:
    return Catalog(data_dir) if data_dir else Catalog()


def sample_users(catalog: Catalog, n: int, seed: int, min_ratings: int = 30) -> list[int]:
    rng = random.Random(seed)
    eligible = [
        uid for uid, hist in catalog.ratings_by_user.items() if len(hist) >= min_ratings
    ]
    rng.shuffle(eligible)
    return eligible[:n]


def dcg(relevances: list[float]) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def ndcg_at_k(recommended_ids: list[int], relevant: set[int], k: int) -> float:
    rels = [1.0 if mid in relevant else 0.0 for mid in recommended_ids[:k]]
    ideal = [1.0] * min(len(relevant), k)
    if not ideal or dcg(ideal) == 0:
        return 0.0
    return dcg(rels) / dcg(ideal)


def hit_at_k(recommended_ids: list[int], relevant: set[int], k: int) -> float:
    return 1.0 if relevant & set(recommended_ids[:k]) else 0.0


def popular_baseline(catalog: Catalog, exclude: set[int], k: int) -> list[int]:
    scored: list[tuple[float, int]] = []
    for movie_id, ratings in catalog.ratings_by_movie.items():
        if movie_id in exclude or movie_id not in catalog.movies:
            continue
        if not ratings:
            continue
        avg = sum(ratings.values()) / len(ratings)
        score = avg + math.log1p(len(ratings))
        scored.append((score, movie_id))
    scored.sort(reverse=True)
    return [mid for _, mid in scored[:k]]


@contextmanager
def temporarily_mask_user_ratings(catalog: Catalog, user_id: int, holdout: set[int]):
    original = catalog.ratings_by_user[user_id]
    catalog.ratings_by_user[user_id] = {
        mid: rating for mid, rating in original.items() if mid not in holdout
    }
    removed: list[tuple[int, float]] = []
    for mid in holdout:
        if user_id in catalog.ratings_by_movie.get(mid, {}):
            removed.append((mid, catalog.ratings_by_movie[mid].pop(user_id)))
    try:
        yield
    finally:
        catalog.ratings_by_user[user_id] = original
        for mid, rating in removed:
            catalog.ratings_by_movie.setdefault(mid, {})[user_id] = rating


def print_report(report: dict[str, Any], out: str | None = None) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if out:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"\nWrote {out_path}", file=sys.stderr)
