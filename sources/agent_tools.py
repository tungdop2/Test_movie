"""JSON tool wrappers bound to a catalog + userId for the orchestrator agent."""

from __future__ import annotations

import json
from typing import Any

from sources.catalog import Catalog
from sources.recommend import build_taste_summary, recommend
from sources.tools import (
    find_candidate_movies,
    find_similar_users,
    get_movie_ratings,
    get_user_history,
    resolve_movie,
)


def _movie_payload(catalog: Catalog, movie, **extra: Any) -> dict[str, Any]:
    avg, n = catalog.movie_avg_rating(movie.movie_id)
    plot = movie.plot or ""
    excerpt = plot if len(plot) <= 280 else plot[:277].rstrip() + "..."
    return {
        "movie_id": movie.movie_id,
        "title": movie.display_title,
        "year": movie.year,
        "genres": list(movie.genres),
        "plot_excerpt": excerpt,
        "catalogue_avg_rating": round(avg, 3) if avg is not None else None,
        "catalogue_rating_count": n,
        **extra,
    }


class ToolBelt:
    """Deterministic tools the LLM may call. user_id is fixed per request."""

    def __init__(self, catalog: Catalog, user_id: int):
        self.catalog = catalog
        self.user_id = user_id
        self.last_neighbor_ids: list[int] = []
        self.tool_trace: list[dict[str, Any]] = []
        self._movies: dict[int, dict[str, Any]] = {}
        self.taste_summary: str | None = None
        self.recommendations: list[dict[str, Any]] = []
        self.peer_opinions: list[dict[str, Any]] = []
        self.compare: list[dict[str, Any]] = []
        self.unresolved_titles: list[str] = []

    def metadata(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "taste_summary": self.taste_summary,
            "movies_found": list(self._movies.values()),
            "recommendations": self.recommendations,
            "peer_opinions": self.peer_opinions,
            "compare": self.compare,
            "unresolved_titles": self.unresolved_titles,
            "tool_trace": self.tool_trace,
        }

    def _remember_movie(self, payload: dict[str, Any]) -> None:
        movie_id = payload.get("movie_id")
        if movie_id is None or "error" in payload:
            return
        self._movies[int(movie_id)] = {
            k: payload[k]
            for k in (
                "movie_id",
                "title",
                "year",
                "genres",
                "plot_excerpt",
                "catalogue_avg_rating",
                "catalogue_rating_count",
            )
            if k in payload
        }

    def as_langchain_tools(self) -> list:
        """Expose ToolBelt methods as LangChain StructuredTools."""
        from langchain_core.tools import StructuredTool
        from pydantic import BaseModel, Field

        class EmptyArgs(BaseModel):
            pass

        class ResolveArgs(BaseModel):
            title: str = Field(description="Movie title to resolve")

        class SimilarUsersArgs(BaseModel):
            k: int = Field(default=40, description="How many neighbors")
            movie_id: int | None = Field(
                default=None,
                description="Optional: restrict to raters of this movie",
            )

        class RatingsArgs(BaseModel):
            movie_id: int
            among_similar_users: bool = Field(
                default=False,
                description="Use last find_similar_users result when true",
            )

        class CandidatesArgs(BaseModel):
            genres: list[str] | None = Field(default=None)
            like_movie_id: int | None = Field(default=None)
            limit: int = Field(default=10)

        class RecommendArgs(BaseModel):
            k: int = Field(default=5)
            genres: list[str] | None = Field(default=None)
            like_movie_id: int | None = Field(default=None)

        class CompareArgs(BaseModel):
            movie_id_a: int
            movie_id_b: int
            k: int = Field(default=40)

        def _wrap(name: str, description: str, schema: type[BaseModel]):
            def _runner(**kwargs):
                # Drop null optionals so handlers keep defaults
                args = {k: v for k, v in kwargs.items() if v is not None}
                return self.call(name, args)

            return StructuredTool.from_function(
                func=_runner,
                name=name,
                description=description,
                args_schema=schema,
            )

        return [
            _wrap(
                "get_taste_summary",
                "Summarise this user's rating taste (genres and liked titles).",
                EmptyArgs,
            ),
            _wrap(
                "resolve_movie",
                "Resolve a free-text movie title to a catalogue movie_id. "
                "Returns found=false if the title is not in the catalogue.",
                ResolveArgs,
            ),
            _wrap(
                "find_similar_users",
                "Find users with similar rating taste. "
                "If movie_id is set, only consider users who rated that movie.",
                SimilarUsersArgs,
            ),
            _wrap(
                "get_movie_ratings_summary",
                "Aggregate ratings for a movie. "
                "Set among_similar_users=true to use the last find_similar_users result.",
                RatingsArgs,
            ),
            _wrap(
                "find_candidate_movies",
                "Find unseen candidate movies for this user, optionally filtered by "
                "genres or similarity to a seed movie_id.",
                CandidatesArgs,
            ),
            _wrap(
                "collaborative_recommend",
                "Recommend unseen movies using similar users (collab) with genre fallback.",
                RecommendArgs,
            ),
            _wrap(
                "compare_movies_for_user",
                "Multi-lookup compare two movies via peer-similar users' ratings.",
                CompareArgs,
            ),
        ]


    def call(self, name: str, arguments: dict[str, Any]) -> str:
        handlers = {
            "get_taste_summary": self._get_taste_summary,
            "resolve_movie": self._resolve_movie,
            "find_similar_users": self._find_similar_users,
            "get_movie_ratings_summary": self._get_movie_ratings_summary,
            "find_candidate_movies": self._find_candidate_movies,
            "collaborative_recommend": self._collaborative_recommend,
            "compare_movies_for_user": self._compare_movies_for_user,
        }
        handler = handlers.get(name)
        if handler is None:
            result: dict[str, Any] = {"error": f"unknown tool: {name}"}
        else:
            try:
                result = handler(arguments)
            except Exception as exc:  # noqa: BLE001 — surface tool errors to the LLM
                result = {"error": str(exc)}

        self.tool_trace.append({"tool": name, "args": arguments, "ok": "error" not in result})
        self._ingest_result(name, result)
        return json.dumps(result, ensure_ascii=False)

    def _ingest_result(self, name: str, result: dict[str, Any]) -> None:
        if name == "get_taste_summary" and result.get("summary"):
            self.taste_summary = result["summary"]
        elif name == "resolve_movie":
            if result.get("found"):
                self._remember_movie(result)
            elif result.get("title_query"):
                self.unresolved_titles.append(result["title_query"])
        elif name == "find_candidate_movies":
            for item in result.get("candidates") or []:
                self._remember_movie(item)
        elif name == "collaborative_recommend":
            if result.get("taste_summary"):
                self.taste_summary = result["taste_summary"]
            recs = result.get("recommendations") or []
            self.recommendations = recs
            for item in recs:
                self._remember_movie(item)
        elif name == "get_movie_ratings_summary" and "movie_id" in result:
            movie = self.catalog.movies.get(int(result["movie_id"]))
            if movie:
                payload = _movie_payload(self.catalog, movie)
                self._remember_movie(payload)
            self.peer_opinions.append(
                {
                    "movie_id": result.get("movie_id"),
                    "title": result.get("title"),
                    "scope": result.get("scope"),
                    "count": result.get("count"),
                    "mean": result.get("mean"),
                    "own_rating": result.get("own_rating"),
                }
            )
        elif name == "compare_movies_for_user":
            movies = result.get("movies") or []
            self.compare = movies
            for item in movies:
                self._remember_movie(item)

    def _get_taste_summary(self, _: dict[str, Any]) -> dict[str, Any]:
        history = get_user_history(self.catalog, self.user_id)
        return {
            "user_id": self.user_id,
            "n_ratings": len(history),
            "summary": build_taste_summary(self.catalog, self.user_id),
        }

    def _resolve_movie(self, args: dict[str, Any]) -> dict[str, Any]:
        title = str(args.get("title") or "").strip()
        resolved = resolve_movie(self.catalog, title)
        if resolved is None:
            return {
                "found": False,
                "title_query": title,
                "message": "Movie not in catalogue (or title could not be matched).",
            }
        return {
            "found": True,
            "match_score": resolved.score,
            "matched_as": resolved.matched_as,
            **_movie_payload(self.catalog, resolved.movie),
        }

    def _find_similar_users(self, args: dict[str, Any]) -> dict[str, Any]:
        k = int(args.get("k") or 40)
        movie_id = args.get("movie_id")
        among = None
        if movie_id is not None:
            among = list(self.catalog.ratings_by_movie.get(int(movie_id), {}))
            if not among:
                return {"neighbors": [], "message": "No raters for that movie_id."}
        neighbors = find_similar_users(
            self.catalog,
            self.user_id,
            k=k,
            among_user_ids=among,
        )
        self.last_neighbor_ids = [n.user_id for n in neighbors]
        return {
            "n_neighbors": len(neighbors),
            "neighbors": [
                {"user_id": n.user_id, "similarity": round(n.similarity, 4)} for n in neighbors[:10]
            ],
            "cached_neighbor_ids": len(self.last_neighbor_ids),
        }

    def _get_movie_ratings_summary(self, args: dict[str, Any]) -> dict[str, Any]:
        movie_id = int(args["movie_id"])
        movie = self.catalog.movies.get(movie_id)
        if movie is None:
            return {"error": "movie_id not in catalogue"}
        among_similar = bool(args.get("among_similar_users"))
        if among_similar:
            if not self.last_neighbor_ids:
                return {
                    "error": "No cached similar users. Call find_similar_users first "
                    "(optionally with this movie_id)."
                }
            ratings = get_movie_ratings(self.catalog, movie_id, self.last_neighbor_ids)
            scope = "similar_users"
        else:
            ratings = get_movie_ratings(self.catalog, movie_id)
            scope = "all_users"
        if not ratings:
            return {
                "movie_id": movie_id,
                "title": movie.display_title,
                "scope": scope,
                "count": 0,
                "mean": None,
                "message": "No ratings in this scope.",
            }
        mean = sum(ratings.values()) / len(ratings)
        own = get_user_history(self.catalog, self.user_id).get(movie_id)
        return {
            "movie_id": movie_id,
            "title": movie.display_title,
            "scope": scope,
            "count": len(ratings),
            "mean": round(mean, 3),
            "own_rating": own,
        }

    def _find_candidate_movies(self, args: dict[str, Any]) -> dict[str, Any]:
        limit = int(args.get("limit") or 10)
        genres = args.get("genres")
        like_movie_id = args.get("like_movie_id")
        movies = find_candidate_movies(
            self.catalog,
            self.user_id,
            genres=list(genres) if genres else None,
            like_movie_id=int(like_movie_id) if like_movie_id is not None else None,
            limit=limit,
        )
        return {
            "count": len(movies),
            "candidates": [_movie_payload(self.catalog, m) for m in movies],
        }

    def _collaborative_recommend(self, args: dict[str, Any]) -> dict[str, Any]:
        result = recommend(
            self.catalog,
            self.user_id,
            genres=list(args["genres"]) if args.get("genres") else None,
            like_movie_id=int(args["like_movie_id"]) if args.get("like_movie_id") is not None else None,
            k=int(args.get("k") or 5),
        )
        return {
            "ok": result.ok,
            "taste_summary": result.taste_summary,
            "recommendations": [
                _movie_payload(self.catalog, r.movie, score=round(r.score, 3), why=r.why)
                for r in result.recommendations
            ],
            "message": result.message if not result.ok else None,
        }

    def _compare_movies_for_user(self, args: dict[str, Any]) -> dict[str, Any]:
        k = int(args.get("k") or 40)
        out: dict[str, Any] = {"movies": []}
        for key in ("movie_id_a", "movie_id_b"):
            movie_id = int(args[key])
            movie = self.catalog.movies.get(movie_id)
            if movie is None:
                out["movies"].append({"movie_id": movie_id, "error": "not in catalogue"})
                continue
            raters = list(self.catalog.ratings_by_movie.get(movie_id, {}))
            neighbors = find_similar_users(
                self.catalog, self.user_id, k=k, among_user_ids=raters
            )
            ratings = get_movie_ratings(
                self.catalog, movie_id, [n.user_id for n in neighbors]
            )
            mean = (sum(ratings.values()) / len(ratings)) if ratings else None
            out["movies"].append(
                {
                    **_movie_payload(self.catalog, movie),
                    "peer_count": len(ratings),
                    "peer_mean": round(mean, 3) if mean is not None else None,
                    "top_neighbor_similarity": round(neighbors[0].similarity, 4) if neighbors else None,
                }
            )
        return out
