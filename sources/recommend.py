"""Personalised recommendations from rating history (hybrid, no LLM)."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from sources.catalog import Catalog, Movie
from sources.tools import find_candidate_movies, find_similar_users, get_user_history

# Global prior for Bayesian average (rough centre of MovieLens ratings).
_PRIOR_MEAN = 3.5
_PRIOR_STRENGTH = 25.0


@dataclass
class Recommendation:
    movie: Movie
    score: float
    why: str


@dataclass
class RecommendResult:
    ok: bool
    recommendations: list[Recommendation]
    taste_summary: str
    message: str


def build_taste_summary(catalog: Catalog, user_id: int, top_n: int = 5) -> str:
    history = get_user_history(catalog, user_id)
    liked = sorted(history.items(), key=lambda x: x[1], reverse=True)[:15]
    genre_counts: dict[str, int] = defaultdict(int)
    liked_titles: list[str] = []
    for movie_id, rating in liked:
        movie = catalog.movies.get(movie_id)
        if not movie:
            continue
        if rating >= 4.0:
            liked_titles.append(movie.display_title)
            for g in movie.genres:
                genre_counts[g] += 1
    top_genres = sorted(genre_counts, key=genre_counts.get, reverse=True)[:top_n]
    parts = []
    if top_genres:
        parts.append("Often rates highly: " + ", ".join(top_genres))
    if liked_titles:
        parts.append("Recent high ratings include: " + "; ".join(liked_titles[:5]))
    return ". ".join(parts) if parts else "Not enough clear genre signal yet."


def _genre_preferences(catalog: Catalog, history: dict[int, float]) -> dict[str, float]:
    weights: dict[str, float] = defaultdict(float)
    for movie_id, rating in history.items():
        if rating < 3.5:
            continue
        movie = catalog.movies.get(movie_id)
        if not movie:
            continue
        for genre in movie.genres:
            weights[genre] += rating - 3.0
    return dict(weights)


def _bayesian_avg(catalog: Catalog, movie_id: int) -> float:
    avg, n = catalog.movie_avg_rating(movie_id)
    if avg is None or n == 0:
        return 0.0
    return (n / (n + _PRIOR_STRENGTH)) * avg + (_PRIOR_STRENGTH / (n + _PRIOR_STRENGTH)) * _PRIOR_MEAN


def _collab_predictions(
    catalog: Catalog,
    user_id: int,
    history: dict[int, float],
) -> dict[int, float]:
    """Similarity-weighted neighbor ratings (mean-centered around 3.0)."""
    neighbors = find_similar_users(catalog, user_id, k=60, min_similarity=0.05)
    numer: dict[int, float] = defaultdict(float)
    denom: dict[int, float] = defaultdict(float)

    for nb in neighbors:
        for movie_id, rating in catalog.ratings_by_user[nb.user_id].items():
            if movie_id in history:
                continue
            if rating < 3.0:
                continue
            numer[movie_id] += nb.similarity * (rating - 3.0)
            denom[movie_id] += nb.similarity

    return {
        movie_id: 3.0 + numer[movie_id] / denom[movie_id]
        for movie_id in numer
        if denom[movie_id] > 0
    }


def _candidate_pool(
    catalog: Catalog,
    history: dict[int, float],
    collab: dict[int, float],
    genre_prefs: dict[str, float],
    *,
    genres: list[str] | None,
    like_movie_id: int | None,
    pool_size: int = 400,
) -> set[int]:
    seen = set(history)
    candidates: set[int] = set(collab)

    # Popular titles (enough support) — personalised by genre when possible.
    popular: list[tuple[float, int]] = []
    preferred = {g.lower() for g in (genres or [])} or {g.lower() for g in genre_prefs}
    if like_movie_id is not None:
        seed = catalog.movies.get(like_movie_id)
        if seed:
            preferred.update(g.lower() for g in seed.genres)

    for movie_id, ratings in catalog.ratings_by_movie.items():
        if movie_id in seen or movie_id not in catalog.movies:
            continue
        if len(ratings) < 8:
            continue
        movie = catalog.movies[movie_id]
        genre_set = {g.lower() for g in movie.genres}
        if preferred and not (preferred & genre_set):
            # keep ultra-popular even if genre miss
            if len(ratings) < 80:
                continue
        popular.append((_bayesian_avg(catalog, movie_id), movie_id))

    popular.sort(reverse=True)
    for _, movie_id in popular[:pool_size]:
        candidates.add(movie_id)

    if genres or like_movie_id is not None:
        allowed = {
            m.movie_id
            for m in find_candidate_movies(
                catalog,
                next(iter(history)) if False else 0,  # placeholder replaced below
                genres=genres,
                like_movie_id=like_movie_id,
                limit=300,
            )
        }
        # find_candidate_movies needs real user_id — caller passes via wrapper
        _ = allowed  # silenced; real filter applied in recommend()

    return candidates


def recommend(
    catalog: Catalog,
    user_id: int,
    *,
    query: str = "",
    genres: list[str] | None = None,
    like_movie_id: int | None = None,
    k: int = 5,
) -> RecommendResult:
    history = get_user_history(catalog, user_id)
    taste = build_taste_summary(catalog, user_id)
    if not history:
        return RecommendResult(
            ok=False,
            recommendations=[],
            taste_summary=taste,
            message="No rating history for this user.",
        )

    genre_prefs = _genre_preferences(catalog, history)
    collab = _collab_predictions(catalog, user_id, history)

    seen = set(history)
    seed = catalog.movies.get(like_movie_id) if like_movie_id is not None else None
    seed_genres = {g.lower() for g in seed.genres} if seed else set()

    # When seeding on a film, candidates must look like that film — not the user's
    # broad taste union (which previously let thrillers through for "like Toy Story").
    if seed_genres:
        preferred_genres = set(seed_genres)
        min_seed_overlap = 2 if len(seed_genres) >= 2 else 1
    else:
        preferred_genres = {g.lower() for g in (genres or [])} or {
            g.lower() for g in genre_prefs
        }
        min_seed_overlap = 0

    candidates: set[int] = set(collab)
    if like_movie_id is not None:
        candidates.discard(like_movie_id)

    popular_scored: list[tuple[float, int]] = []
    for movie_id, ratings in catalog.ratings_by_movie.items():
        if movie_id in seen or movie_id not in catalog.movies:
            continue
        if like_movie_id is not None and movie_id == like_movie_id:
            continue
        if len(ratings) < 8:
            continue
        movie = catalog.movies[movie_id]
        genre_set = {g.lower() for g in movie.genres}
        if seed_genres:
            if len(seed_genres & genre_set) < min_seed_overlap:
                continue
        elif preferred_genres and not (preferred_genres & genre_set) and len(ratings) < 80:
            continue
        popular_scored.append((_bayesian_avg(catalog, movie_id), movie_id))
    popular_scored.sort(reverse=True)
    for _, movie_id in popular_scored[:400]:
        candidates.add(movie_id)

    if genres or like_movie_id is not None:
        allowed = {
            m.movie_id
            for m in find_candidate_movies(
                catalog,
                user_id,
                genres=genres,
                like_movie_id=like_movie_id,
                limit=400,
            )
        }
        if like_movie_id is not None:
            allowed.discard(like_movie_id)
        candidates &= allowed
        if not candidates:
            candidates = allowed

    # Seed mode: drop anything that still fails the seed-genre bar after intersect.
    if seed_genres:
        candidates = {
            mid
            for mid in candidates
            if mid in catalog.movies
            and len(seed_genres & {g.lower() for g in catalog.movies[mid].genres})
            >= min_seed_overlap
        }

    genre_pref_total = sum(genre_prefs.values()) or 1.0
    scored: list[Recommendation] = []

    for movie_id in candidates:
        movie = catalog.movies.get(movie_id)
        if not movie:
            continue
        pop = _bayesian_avg(catalog, movie_id)
        pred = collab.get(movie_id)
        genre_overlap = sum(genre_prefs.get(g, 0.0) for g in movie.genres) / genre_pref_total
        movie_genres = {g.lower() for g in movie.genres}
        seed_overlap = len(seed_genres & movie_genres)
        seed_jaccard = (
            seed_overlap / len(seed_genres | movie_genres) if seed_genres else 0.0
        )

        pop_n = pop / 5.0
        col_n = (pred / 5.0) if pred is not None else pop_n * 0.85
        if seed_genres:
            # Seed similarity dominates; light personalisation / quality only.
            final = (
                0.55 * seed_jaccard
                + 0.20 * min(seed_overlap / max(len(seed_genres), 1), 1.0)
                + 0.15 * pop_n
                + 0.10 * col_n
            )
        else:
            final = 0.45 * pop_n + 0.35 * col_n + 0.20 * min(max(genre_overlap, 0.0), 1.0)
            if pred is not None:
                final += 0.03

        _, n = catalog.movie_avg_rating(movie_id)
        why_parts = [f"catalogue quality ~{pop:.2f}/5 ({n} ratings)"]
        if seed is not None:
            shared = sorted(seed_genres & movie_genres)
            why_parts.insert(
                0,
                f"similar to {seed.display_title} via genres: {', '.join(shared) or 'n/a'}",
            )
        if pred is not None and not seed_genres:
            why_parts.append(f"similar users ~{pred:.2f}/5")
        if genre_overlap > 0.05 and not seed_genres:
            why_parts.append("matches your frequent genres")
        scored.append(
            Recommendation(
                movie=movie,
                score=final,
                why="; ".join(why_parts),
            )
        )

    scored.sort(key=lambda r: r.score, reverse=True)
    # Diversify a little: limit very niche (n<15) in top slots unless collab-strong
    recommendations: list[Recommendation] = []
    for rec in scored:
        avg, n = catalog.movie_avg_rating(rec.movie.movie_id)
        if n < 15 and rec.movie.movie_id not in collab and len(recommendations) < k:
            continue
        recommendations.append(rec)
        if len(recommendations) >= k:
            break

    if len(recommendations) < k:
        have = {r.movie.movie_id for r in recommendations}
        for rec in scored:
            if rec.movie.movie_id in have:
                continue
            recommendations.append(rec)
            if len(recommendations) >= k:
                break

    if not recommendations:
        return RecommendResult(
            ok=False,
            recommendations=[],
            taste_summary=taste,
            message="I could not find suitable unseen movies for this user with current filters.",
        )

    lines = [
        f"- {r.movie.display_title} [{', '.join(r.movie.genres[:3])}] — {r.why}"
        for r in recommendations
    ]
    message = (
        f"Based on your rating history ({len(history)} films):\n"
        f"{taste}\n\n"
        f"Suggestions for: {query or 'what to watch'}\n"
        + "\n".join(lines)
    )
    return RecommendResult(
        ok=True,
        recommendations=recommendations,
        taste_summary=taste,
        message=message,
    )
