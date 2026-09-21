#!/usr/bin/env python3
"""Decline-gate eval (no LLM): unknown user / unknown movie / real controls.

  uv run python scripts/eval_decline.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eval_lib import load_catalog, print_report
from sources.decline import check_movie_if_needed, check_user
from sources.tools import resolve_movie


def eval_decline(catalog) -> dict[str, Any]:
    fake_users = [900_001 + i for i in range(20)]
    fake_titles = [
        "Avatar 2099",
        "Completely Fake Movie XYZ",
        "The Matrix Reloaded 3000",
        "Unknown Film Qwerty",
        "Dune Part Zero",
    ] * 4

    unknown_user_ok = sum(1 for uid in fake_users if check_user(catalog, uid).declined)

    unknown_movie_ok = 0
    for title in fake_titles:
        resolved = resolve_movie(catalog, title)
        declined = check_movie_if_needed(catalog, title, required=True).declined
        if resolved is None and declined:
            unknown_movie_ok += 1

    real_user = next(iter(catalog.user_ids()))
    control_user_ok = not check_user(catalog, real_user).declined
    pulp = resolve_movie(catalog, "Pulp Fiction")
    control_movie_ok = pulp is not None and not check_movie_if_needed(
        catalog, "Pulp Fiction", required=True
    ).declined

    return {
        "unknown_user_accuracy": round(unknown_user_ok / len(fake_users), 4),
        "unknown_user_n": len(fake_users),
        "unknown_movie_accuracy": round(unknown_movie_ok / len(fake_titles), 4),
        "unknown_movie_n": len(fake_titles),
        "control_real_user_accepted": control_user_ok,
        "control_real_movie_accepted": control_movie_ok,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval decline gate (no LLM)")
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args(argv)

    catalog = load_catalog(args.data_dir)
    report = {
        "eval": "decline",
        "llm_used": False,
        "results": eval_decline(catalog),
    }
    print_report(report, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
