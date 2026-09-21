"""Load MovieLens CSVs and keep simple in-memory indexes."""

from __future__ import annotations

import csv
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "ml-latest-small-filtered"


@dataclass(frozen=True)
class Movie:
    movie_id: int
    title: str
    year: int | None
    genres: tuple[str, ...]
    plot: str = ""

    @property
    def display_title(self) -> str:
        if self.year:
            return f"{self.title} ({self.year})"
        return self.title


def _parse_year(raw: str) -> int | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


class Catalog:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.movies: dict[int, Movie] = {}
        self.ratings_by_user: dict[int, dict[int, float]] = defaultdict(dict)
        self.ratings_by_movie: dict[int, dict[int, float]] = defaultdict(dict)
        self._title_index: list[tuple[str, int]] = []
        self._load()

    def _load(self) -> None:
        movies_path = self.data_dir / "movies_with_plots.csv"
        ratings_path = self.data_dir / "ratings.csv"
        if not movies_path.exists() or not ratings_path.exists():
            raise FileNotFoundError(f"Expected CSVs under {self.data_dir}")

        with movies_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                movie_id = int(row["movieId"])
                genres = tuple(g for g in row.get("genres", "").split("|") if g and g != "(no genres listed)")
                movie = Movie(
                    movie_id=movie_id,
                    title=row["title"].strip(),
                    year=_parse_year(row.get("year", "")),
                    genres=genres,
                    plot=(row.get("plot") or "").strip(),
                )
                self.movies[movie_id] = movie
                key = self._normalize_title(movie.title)
                self._title_index.append((key, movie_id))

        with ratings_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                user_id = int(row["userId"])
                movie_id = int(row["movieId"])
                rating = float(row["rating"])
                self.ratings_by_user[user_id][movie_id] = rating
                self.ratings_by_movie[movie_id][user_id] = rating

        # freeze as plain dicts
        self.ratings_by_user = dict(self.ratings_by_user)
        self.ratings_by_movie = dict(self.ratings_by_movie)

    @staticmethod
    def _normalize_title(title: str) -> str:
        title = title.lower().strip()
        title = re.sub(r"\s*\(\d{4}\)\s*$", "", title)
        title = re.sub(r"[^a-z0-9\s]", " ", title)
        return re.sub(r"\s+", " ", title).strip()

    def has_user(self, user_id: int) -> bool:
        return user_id in self.ratings_by_user and bool(self.ratings_by_user[user_id])

    def user_ids(self) -> list[int]:
        return sorted(self.ratings_by_user)

    def movie_avg_rating(self, movie_id: int) -> tuple[float | None, int]:
        scores = self.ratings_by_movie.get(movie_id, {})
        if not scores:
            return None, 0
        return sum(scores.values()) / len(scores), len(scores)


def cosine_similarity(a: dict[int, float], b: dict[int, float]) -> float:
    shared = set(a) & set(b)
    if len(shared) < 2:
        return 0.0
    dot = sum(a[i] * b[i] for i in shared)
    norm_a = math.sqrt(sum(a[i] * a[i] for i in shared))
    norm_b = math.sqrt(sum(b[i] * b[i] for i in shared))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
