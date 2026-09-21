"""Deterministic decline rules for unknown users / movies."""

from __future__ import annotations

from dataclasses import dataclass

from sources.catalog import Catalog
from sources.tools import ResolvedMovie, resolve_movie


@dataclass
class DeclineResult:
    declined: bool
    reason: str = ""
    message: str = ""
    resolved_movie: ResolvedMovie | None = None


def check_user(catalog: Catalog, user_id: int) -> DeclineResult:
    if not catalog.has_user(user_id):
        return DeclineResult(
            declined=True,
            reason="unknown_user",
            message=(
                f"No rating history for userId={user_id}. "
                "I cannot personalise recommendations without prior ratings."
            ),
        )
    return DeclineResult(declined=False)


def check_movie_if_needed(
    catalog: Catalog,
    title: str | None,
    *,
    required: bool,
) -> DeclineResult:
    if not title:
        if required:
            return DeclineResult(
                declined=True,
                reason="missing_movie",
                message="I need a movie title from the catalogue to answer that.",
            )
        return DeclineResult(declined=False)

    resolved = resolve_movie(catalog, title)
    if resolved is None:
        return DeclineResult(
            declined=True,
            reason="unknown_movie",
            message=(
                f"'{title}' is not in this catalogue (or I could not match the title). "
                "I can only answer from movies present in the dataset."
            ),
        )
    return DeclineResult(declined=False, resolved_movie=resolved)
