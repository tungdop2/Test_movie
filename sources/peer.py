"""PeerTaste — multi-lookup: similar users + movie ratings."""

from __future__ import annotations

from dataclasses import dataclass

from sources.catalog import Catalog
from sources.tools import (
    ResolvedMovie,
    find_similar_users,
    get_movie_ratings,
    get_user_history,
)


@dataclass
class PeerOpinionResult:
    ok: bool
    message: str
    mean: float | None = None
    count: int = 0
    movie_title: str = ""


def peer_opinion(
    catalog: Catalog,
    user_id: int,
    resolved: ResolvedMovie,
    *,
    neighbor_k: int = 40,
) -> PeerOpinionResult:
    """What do people with taste like mine think of movie X?

    Lookups:
      1) user history / similar users
      2) ratings of X among those neighbors
    """
    history = get_user_history(catalog, user_id)
    movie_id = resolved.movie.movie_id
    raters = list(catalog.ratings_by_movie.get(movie_id, {}))
    if not raters:
        return PeerOpinionResult(
            ok=False,
            message=f"No ratings exist for {resolved.movie.display_title} in this dataset.",
            movie_title=resolved.movie.display_title,
            count=0,
        )

    # Prefer neighbors who actually rated the target movie (multi-lookup).
    neighbors = find_similar_users(
        catalog,
        user_id,
        k=neighbor_k,
        among_user_ids=raters,
    )
    if not neighbors:
        return PeerOpinionResult(
            ok=False,
            message=(
                f"No sufficiently similar users who rated "
                f"{resolved.movie.display_title}."
            ),
            movie_title=resolved.movie.display_title,
        )

    neighbor_ids = [n.user_id for n in neighbors]
    peer_ratings = get_movie_ratings(catalog, movie_id, neighbor_ids)
    mean = sum(peer_ratings.values()) / len(peer_ratings)
    own = history.get(movie_id)
    own_line = f" Your own rating on file: {own}/5." if own is not None else ""

    top_sims = ", ".join(f"u{n.user_id}({n.similarity:.2f})" for n in neighbors[:5])
    message = (
        f"Among {len(peer_ratings)} users with taste similar to yours "
        f"who rated this film (e.g. {top_sims}), "
        f"{resolved.movie.display_title} averages {mean:.2f}/5."
        f"{own_line}"
    )
    return PeerOpinionResult(
        ok=True,
        message=message,
        mean=mean,
        count=len(peer_ratings),
        movie_title=resolved.movie.display_title,
    )
