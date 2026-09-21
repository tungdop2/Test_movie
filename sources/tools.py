"""Shared lookup tools (multi-lookup = chaining these)."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from sources.catalog import Catalog, Movie, cosine_similarity


@dataclass
class ResolvedMovie:
    movie: Movie
    score: float
    matched_as: str


@dataclass
class Neighbor:
    user_id: int
    similarity: float


def get_user_history(catalog: Catalog, user_id: int) -> dict[int, float]:
    return dict(catalog.ratings_by_user.get(user_id, {}))


def _token_boundary_contains(haystack: str, needle: str) -> bool:
    """True if needle appears as a whole token sequence inside haystack."""
    if not needle or needle not in haystack:
        return False
    # Avoid matching "9" inside "2099"
    parts = haystack.split()
    needle_parts = needle.split()
    if not needle_parts:
        return False
    n = len(needle_parts)
    for i in range(len(parts) - n + 1):
        if parts[i : i + n] == needle_parts:
            return True
    return False


def resolve_movie(catalog: Catalog, title_query: str, min_score: float = 0.88) -> ResolvedMovie | None:
    """Map a free-text title to a catalogue movie, or None if not found."""
    import re

    query = Catalog._normalize_title(title_query)
    if not query:
        return None

    year_match = re.search(r"\b((?:19|20)\d{2})\b", query)
    query_year = int(year_match.group(1)) if year_match else None
    query_wo_year = re.sub(r"\b(?:19|20)\d{2}\b", "", query).strip()
    query_wo_year = re.sub(r"\s+", " ", query_wo_year)

    best: ResolvedMovie | None = None
    for key, movie_id in catalog._title_index:
        movie = catalog.movies[movie_id]
        if query_year is not None and movie.year is not None and movie.year != query_year:
            continue

        compare = query_wo_year if query_year is not None else query
        if not compare:
            continue

        if compare == key:
            return ResolvedMovie(movie=movie, score=1.0, matched_as="exact")

        # Query is a shorter form of the catalogue title (e.g. "pulp fiction")
        if len(compare) >= 5 and _token_boundary_contains(key, compare):
            candidate = ResolvedMovie(movie=movie, score=0.95, matched_as="substring")
        # Catalogue title appears inside a longer query — require substantial title
        elif (
            len(key) >= 6
            and len(key) >= max(6, int(0.6 * len(compare)))
            and _token_boundary_contains(compare, key)
        ):
            candidate = ResolvedMovie(movie=movie, score=0.90, matched_as="substring")
        else:
            ratio = SequenceMatcher(None, compare, key).ratio()
            # Fuzzy only when lengths are comparable (avoids "avatar 2099" → random hits)
            len_ratio = min(len(compare), len(key)) / max(len(compare), len(key))
            if ratio < min_score or len_ratio < 0.75:
                continue
            candidate = ResolvedMovie(movie=movie, score=ratio, matched_as="fuzzy")

        if best is None or candidate.score > best.score:
            best = candidate

    if best and best.score >= min_score:
        return best
    return None


def find_similar_users(
    catalog: Catalog,
    user_id: int,
    k: int = 30,
    min_similarity: float = 0.1,
    *,
    among_user_ids: list[int] | None = None,
) -> list[Neighbor]:
    history = catalog.ratings_by_user.get(user_id, {})
    if not history:
        return []

    if among_user_ids is None:
        candidates = catalog.ratings_by_user.keys()
    else:
        candidates = among_user_ids

    neighbors: list[Neighbor] = []
    for other_id in candidates:
        if other_id == user_id:
            continue
        other_hist = catalog.ratings_by_user.get(other_id)
        if not other_hist:
            continue
        sim = cosine_similarity(history, other_hist)
        if sim >= min_similarity:
            neighbors.append(Neighbor(user_id=other_id, similarity=sim))

    neighbors.sort(key=lambda n: n.similarity, reverse=True)
    return neighbors[:k]


def get_movie_ratings(
    catalog: Catalog,
    movie_id: int,
    user_ids: list[int] | None = None,
) -> dict[int, float]:
    all_ratings = catalog.ratings_by_movie.get(movie_id, {})
    if user_ids is None:
        return dict(all_ratings)
    wanted = set(user_ids)
    return {uid: score for uid, score in all_ratings.items() if uid in wanted}


def find_candidate_movies(
    catalog: Catalog,
    user_id: int,
    *,
    genres: list[str] | None = None,
    like_movie_id: int | None = None,
    exclude_seen: bool = True,
    limit: int = 50,
) -> list[Movie]:
    """Candidate pool for recommend / 'like X but for me' style questions."""
    history = catalog.ratings_by_user.get(user_id, {})
    seen = set(history) if exclude_seen else set()

    preferred_genres: set[str] = set()
    if genres:
        preferred_genres = {g.lower() for g in genres}
    else:
        for mid, rating in history.items():
            if rating < 4.0:
                continue
            movie = catalog.movies.get(mid)
            if movie:
                preferred_genres.update(g.lower() for g in movie.genres)

    if like_movie_id is not None:
        seed = catalog.movies.get(like_movie_id)
        if seed:
            # Seed similarity mode: overlap against the seed film only.
            preferred_genres = {g.lower() for g in seed.genres}

    scored: list[tuple[float, Movie]] = []
    min_overlap = 2 if like_movie_id is not None and len(preferred_genres) >= 2 else 1
    for movie in catalog.movies.values():
        if movie.movie_id in seen:
            continue
        if like_movie_id is not None and movie.movie_id == like_movie_id:
            continue
        genre_set = {g.lower() for g in movie.genres}
        overlap = len(preferred_genres & genre_set)
        if preferred_genres and overlap < min_overlap:
            continue
        avg, n = catalog.movie_avg_rating(movie.movie_id)
        popularity = math_log_count(n)
        score = overlap * 2.0 + (avg or 0.0) + popularity
        if like_movie_id is not None and preferred_genres:
            score += overlap * 3.0
        scored.append((score, movie))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:limit]]


def math_log_count(n: int) -> float:
    import math

    return math.log1p(n)
