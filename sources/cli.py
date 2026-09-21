#!/usr/bin/env python3
"""CLI demo — one orchestrator agent + tools.

Examples:
  uv run python -m sources.cli --user 1 --query "what should I watch tonight?"
  uv run python -m sources.cli --user 1 --query "what do people with taste like mine think of Pulp Fiction?"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sources.assistant import MovieAssistant
from sources.catalog import Catalog
from sources.settings import get_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Movie assistant (orchestrator agent)")
    parser.add_argument("--user", type=int, required=True, help="MovieLens userId")
    parser.add_argument("--query", type=str, required=True, help="Natural language question")
    parser.add_argument("--data-dir", type=str, default=None, help="Optional dataset path")
    args = parser.parse_args(argv)

    settings = get_settings()
    catalog = Catalog(args.data_dir) if args.data_dir else Catalog(settings.data_dir)
    assistant = MovieAssistant(catalog, settings)
    reply = assistant.ask(args.user, args.query)

    print(f"intent: {reply.intent}")
    print(f"declined: {reply.declined}")
    if reply.used_fallback:
        print("mode: fallback (deterministic)")
    if reply.tool_calls:
        print(f"tools: {', '.join(reply.tool_calls)}")
    print()
    print(reply.message)
    print()
    print("--- metadata ---")
    print(json.dumps(reply.metadata, ensure_ascii=False, indent=2))
    return 0 if not reply.declined else 2


if __name__ == "__main__":
    raise SystemExit(main())
