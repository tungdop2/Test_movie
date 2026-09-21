"""Deterministic fallback when the LLM agent is unavailable."""

from __future__ import annotations

import re
from typing import Any

from sources.agent_tools import _movie_payload
from sources.catalog import Catalog
from sources.decline import check_movie_if_needed
from sources.peer import peer_opinion
from sources.recommend import recommend

PEER_HINTS = (
    "think of",
    "think about",
    "opinion",
    "people like me",
    "taste like mine",
    "similar users",
    "gu giống",
    "nghĩ gì",
    "or ",
    " vs ",
    "compare",
)


def _extract_movie_title(catalog: Catalog, query: str) -> str | None:
    quoted = re.search(r"[\"']([^\"']+)[\"']", query)
    if quoted:
        return quoted.group(1).strip()

    patterns = [
        r"think(?:s)? of (.+)$",
        r"think(?:s)? about (.+)$",
        r"opinion on (.+)$",
        r"opinion of (.+)$",
        r"like (.+)$",
        r"similar to (.+)$",
        r"giống (.+)$",
        r"về (.+)$",
    ]
    for pat in patterns:
        m = re.search(pat, query.strip(), flags=re.IGNORECASE)
        if m:
            return re.sub(r"\?+$", "", m.group(1)).strip(" ?.!,")

    qn = Catalog._normalize_title(query)
    best_title = None
    best_len = 0
    for key, movie_id in catalog._title_index:
        if len(key) < 4:
            continue
        if key in qn and len(key) > best_len:
            best_len = len(key)
            best_title = catalog.movies[movie_id].title
    return best_title


def _base_meta(user_id: int) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "taste_summary": None,
        "movies_found": [],
        "recommendations": [],
        "peer_opinions": [],
        "compare": [],
        "unresolved_titles": [],
        "tool_trace": [{"tool": "fallback", "args": {}, "ok": True}],
    }


def run_fallback(
    catalog: Catalog, user_id: int, query: str
) -> tuple[str, bool, str, dict[str, Any]]:
    """Return (intent, declined, message, metadata)."""
    q = query.lower()
    title = _extract_movie_title(catalog, query)
    meta = _base_meta(user_id)

    if " or " in q or " vs " in q or "compare" in q:
        movie_check = check_movie_if_needed(catalog, title, required=True)
        if movie_check.declined:
            if title:
                meta["unresolved_titles"].append(title)
            return "decline", True, movie_check.message, meta
        assert movie_check.resolved_movie is not None
        movie = movie_check.resolved_movie.movie
        result = peer_opinion(catalog, user_id, movie_check.resolved_movie)
        payload = _movie_payload(catalog, movie)
        meta["movies_found"] = [payload]
        meta["peer_opinions"] = [
            {
                "movie_id": movie.movie_id,
                "title": movie.display_title,
                "mean": result.mean,
                "count": result.count,
            }
        ]
        return (
            "peer_opinion",
            not result.ok,
            result.message + " (fallback; compare needs the LLM agent)",
            meta,
        )

    if any(h in q for h in PEER_HINTS if h not in (" or ", " vs ", "compare")):
        movie_check = check_movie_if_needed(catalog, title, required=True)
        if movie_check.declined:
            if title:
                meta["unresolved_titles"].append(title)
            return "decline", True, movie_check.message, meta
        assert movie_check.resolved_movie is not None
        movie = movie_check.resolved_movie.movie
        result = peer_opinion(catalog, user_id, movie_check.resolved_movie)
        payload = _movie_payload(catalog, movie)
        meta["movies_found"] = [payload]
        meta["peer_opinions"] = [
            {
                "movie_id": movie.movie_id,
                "title": movie.display_title,
                "mean": result.mean,
                "count": result.count,
            }
        ]
        return "peer_opinion", not result.ok, result.message, meta

    if re.search(r"\b(like|similar to|giống)\b", q):
        movie_check = check_movie_if_needed(catalog, title, required=True)
        if movie_check.declined:
            if title:
                meta["unresolved_titles"].append(title)
            return "decline", True, movie_check.message, meta
        assert movie_check.resolved_movie is not None
        seed = movie_check.resolved_movie.movie
        result = recommend(
            catalog,
            user_id,
            query=query,
            like_movie_id=seed.movie_id,
        )
        meta["taste_summary"] = result.taste_summary
        meta["movies_found"] = [_movie_payload(catalog, seed)]
        meta["recommendations"] = [
            _movie_payload(catalog, r.movie, score=round(r.score, 3), why=r.why)
            for r in result.recommendations
        ]
        meta["movies_found"].extend(meta["recommendations"])
        return "like_movie", not result.ok, result.message, meta

    result = recommend(catalog, user_id, query=query)
    meta["taste_summary"] = result.taste_summary
    meta["recommendations"] = [
        _movie_payload(catalog, r.movie, score=round(r.score, 3), why=r.why)
        for r in result.recommendations
    ]
    meta["movies_found"] = list(meta["recommendations"])
    return "recommend", not result.ok, result.message, meta
