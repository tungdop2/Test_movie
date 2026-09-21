#!/usr/bin/env python3
"""Agent eval (20 fixed questions).

1) Tools / decline / metadata shape — deterministic
2) Natural-language output — LLM-as-judge (grounded + task fit)

  uv run python scripts/eval_agent.py --out docs/samples/eval_agent_results.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eval_lib import load_catalog, print_report
from sources.assistant import MovieAssistant
from sources.settings import Settings, get_settings


@dataclass
class Case:
    id: str
    user_id: int
    query: str
    expect_declined: bool
    notes: str = ""
    require_tools: list[str] = field(default_factory=list)
    require_any_tool: list[str] = field(default_factory=list)
    require_recommendations: bool = False
    require_peer_opinion: bool = False
    require_movies_found: bool = False
    require_unresolved: bool = False
    allow_no_agent: bool = False
    # Title substrings that should appear in movies_found / recommendations / peer.
    expect_movies_contain: list[str] = field(default_factory=list)
    # Short rubric for the LLM judge.
    judge_rubric: str = ""

    def expected_block(self) -> dict[str, Any]:
        return {
            "declined": self.expect_declined,
            "require_tools_all": self.require_tools,
            "require_tools_any": self.require_any_tool,
            "require_recommendations": self.require_recommendations,
            "require_peer_opinion": self.require_peer_opinion,
            "require_movies_found": self.require_movies_found,
            "require_unresolved": self.require_unresolved,
            "expect_movies_contain": self.expect_movies_contain,
            "allow_no_agent": self.allow_no_agent,
            "notes": self.notes,
            "judge_rubric": self.judge_rubric,
        }


CASES: list[Case] = [
    Case(
        id="R01",
        user_id=1,
        query="what should I watch tonight?",
        expect_declined=False,
        require_any_tool=["collaborative_recommend", "find_candidate_movies", "get_taste_summary"],
        require_recommendations=True,
        require_movies_found=True,
        notes="personalised recommend",
        judge_rubric="Should suggest concrete catalogue movies and briefly tie them to the user's taste.",
    ),
    Case(
        id="R02",
        user_id=7,
        query="recommend something for me based on my ratings",
        expect_declined=False,
        require_any_tool=["collaborative_recommend", "get_taste_summary"],
        require_recommendations=True,
        require_movies_found=True,
        judge_rubric="Should recommend movies consistent with tool evidence, not invent titles.",
    ),
    Case(
        id="R03",
        user_id=15,
        query="tối nay xem gì?",
        expect_declined=False,
        require_any_tool=["collaborative_recommend", "get_taste_summary"],
        require_recommendations=True,
        require_movies_found=True,
        notes="Vietnamese query",
        judge_rubric="May answer in Vietnamese; suggestions must match tool metadata.",
    ),
    Case(
        id="R04",
        user_id=42,
        query="give me 5 movie suggestions matching my taste",
        expect_declined=False,
        require_any_tool=["collaborative_recommend"],
        require_recommendations=True,
        require_movies_found=True,
        judge_rubric="Should offer multiple suggestions aligned with recommendations metadata.",
    ),
    Case(
        id="P01",
        user_id=1,
        query="what do people with taste like mine think of Pulp Fiction?",
        expect_declined=False,
        require_tools=["resolve_movie", "find_similar_users", "get_movie_ratings_summary"],
        require_peer_opinion=True,
        require_movies_found=True,
        expect_movies_contain=["Pulp Fiction"],
        notes="canonical multi-lookup",
        judge_rubric="Must discuss Pulp Fiction and report peer rating consistent with peer_opinions metadata.",
    ),
    Case(
        id="P02",
        user_id=1,
        query="how do similar users rate Fight Club?",
        expect_declined=False,
        require_tools=["resolve_movie"],
        require_any_tool=["get_movie_ratings_summary", "find_similar_users", "compare_movies_for_user"],
        require_movies_found=True,
        expect_movies_contain=["Fight Club"],
        judge_rubric="Must be about Fight Club and use peer/similar-user evidence from tools.",
    ),
    Case(
        id="P03",
        user_id=7,
        query="people like me — opinion on Inception?",
        expect_declined=False,
        require_tools=["resolve_movie"],
        require_any_tool=["get_movie_ratings_summary", "find_similar_users"],
        require_peer_opinion=True,
        require_movies_found=True,
        expect_movies_contain=["Inception"],
        judge_rubric="Must be about Inception with a peer mean consistent with metadata.",
    ),
    Case(
        id="P04",
        user_id=15,
        query="what do people with taste like mine think of Toy Story?",
        expect_declined=False,
        require_tools=["resolve_movie", "find_similar_users", "get_movie_ratings_summary"],
        require_peer_opinion=True,
        require_movies_found=True,
        expect_movies_contain=["Toy Story"],
        judge_rubric="Must be about Toy Story with peer evidence.",
    ),
    Case(
        id="L01",
        user_id=1,
        query="recommend something like Toy Story",
        expect_declined=False,
        require_tools=["resolve_movie"],
        require_any_tool=["collaborative_recommend", "find_candidate_movies"],
        require_movies_found=True,
        expect_movies_contain=["Toy Story"],
        judge_rubric="Should acknowledge Toy Story as seed and suggest similar catalogue titles from tools.",
    ),
    Case(
        id="L02",
        user_id=7,
        query="movies similar to Pulp Fiction that fit my taste",
        expect_declined=False,
        require_tools=["resolve_movie"],
        require_any_tool=["collaborative_recommend", "find_candidate_movies"],
        require_movies_found=True,
        expect_movies_contain=["Pulp Fiction"],
        judge_rubric="Should treat Pulp Fiction as seed and recommend from tool results.",
    ),
    Case(
        id="C01",
        user_id=1,
        query="Pulp Fiction or Fight Club — which fits my taste better?",
        expect_declined=False,
        require_any_tool=["compare_movies_for_user", "resolve_movie"],
        require_movies_found=True,
        expect_movies_contain=["Pulp Fiction", "Fight Club"],
        notes="compare / multi-entity",
        judge_rubric="Must compare both films using tool evidence and pick or weigh them clearly.",
    ),
    Case(
        id="C02",
        user_id=42,
        query="compare Alien and Aliens for someone with my ratings",
        expect_declined=False,
        require_any_tool=["compare_movies_for_user", "resolve_movie", "get_movie_ratings_summary"],
        require_movies_found=True,
        expect_movies_contain=["Alien"],
        judge_rubric="Must compare Alien and Aliens with evidence from tools.",
    ),
    Case(
        id="D01",
        user_id=99999,
        query="what should I watch tonight?",
        expect_declined=True,
        allow_no_agent=True,
        notes="unknown user",
        judge_rubric="Must refuse personalisation because the user has no rating history.",
    ),
    Case(
        id="D02",
        user_id=900001,
        query="recommend a comedy",
        expect_declined=True,
        allow_no_agent=True,
        judge_rubric="Must refuse due to unknown/no-history user.",
    ),
    Case(
        id="D03",
        user_id=900002,
        query="what do people with taste like mine think of Pulp Fiction?",
        expect_declined=True,
        allow_no_agent=True,
        judge_rubric="Must refuse due to unknown/no-history user.",
    ),
    Case(
        id="D04",
        user_id=1,
        query="what do people with taste like mine think of Avatar 2099?",
        expect_declined=True,
        require_any_tool=["resolve_movie"],
        require_unresolved=True,
        notes="unknown title",
        judge_rubric="Must refuse because the title is outside the catalogue.",
    ),
    Case(
        id="D05",
        user_id=1,
        query="what do people with taste like mine think of Completely Fake Movie XYZ?",
        expect_declined=True,
        require_any_tool=["resolve_movie"],
        require_unresolved=True,
        judge_rubric="Must refuse because the title is outside the catalogue.",
    ),
    Case(
        id="D06",
        user_id=7,
        query="recommend something like Dune Part Zero",
        expect_declined=True,
        require_any_tool=["resolve_movie"],
        require_unresolved=True,
        judge_rubric="Must refuse because the seed title is outside the catalogue.",
    ),
    Case(
        id="G01",
        user_id=1,
        query="in thrillers I have not seen, what do similar users like?",
        expect_declined=False,
        require_any_tool=[
            "find_similar_users",
            "find_candidate_movies",
            "collaborative_recommend",
            "get_taste_summary",
        ],
        require_movies_found=True,
        notes="broader multi-lookup 1.2",
        judge_rubric="Should recommend thrillers grounded in tool results / user taste.",
    ),
    Case(
        id="G02",
        user_id=15,
        query="why might I like Se7en based on my history?",
        expect_declined=False,
        require_tools=["resolve_movie"],
        require_any_tool=["get_taste_summary", "get_movie_ratings_summary", "find_similar_users"],
        require_movies_found=True,
        expect_movies_contain=["Seven", "Se7en"],
        notes="explain / evidence lookup",
        judge_rubric="Must explain Se7en/Seven using taste or peer evidence from tools; no invented facts.",
    ),
]


class JudgeVerdict(BaseModel):
    passed: bool = Field(description="Whether the assistant output passes the rubric")
    grounded_score: int = Field(ge=1, le=5, description="1=invents facts, 5=fully grounded in evidence")
    task_fit_score: int = Field(ge=1, le=5, description="1=wrong task, 5=fully answers/refuses correctly")
    rationale: str = Field(description="Brief justification")


def score_tools(case: Case, reply) -> dict[str, Any]:
    meta = reply.metadata or {}
    tools = list(reply.tool_calls or [])
    checks: dict[str, bool] = {}
    failures: list[str] = []

    checks["declined_ok"] = reply.declined is case.expect_declined
    if not checks["declined_ok"]:
        failures.append(f"declined={reply.declined}, expected={case.expect_declined}")

    if reply.used_fallback and not case.allow_no_agent:
        checks["not_fallback"] = False
        failures.append("used deterministic fallback instead of agent")
    else:
        checks["not_fallback"] = True

    if case.require_tools:
        missing = [t for t in case.require_tools if t not in tools]
        checks["require_tools"] = not missing
        if missing:
            failures.append(f"missing required tools {missing}")
    else:
        checks["require_tools"] = True

    if case.require_any_tool:
        ok = any(t in tools for t in case.require_any_tool) or (
            case.allow_no_agent and case.expect_declined and not tools
        )
        checks["require_any_tool"] = ok
        if not ok:
            failures.append(f"expected one of {case.require_any_tool}, got {tools}")
    else:
        checks["require_any_tool"] = True

    recs = meta.get("recommendations") or []
    if case.require_recommendations:
        checks["recommendations"] = len(recs) > 0
        if not checks["recommendations"]:
            failures.append("recommendations empty")
    else:
        checks["recommendations"] = True

    peers = meta.get("peer_opinions") or []
    if case.require_peer_opinion:
        checks["peer_opinion"] = len(peers) > 0 and peers[0].get("mean") is not None
        if not checks["peer_opinion"]:
            failures.append("peer_opinions missing")
    else:
        checks["peer_opinion"] = True

    movies = meta.get("movies_found") or []
    if case.require_movies_found:
        checks["movies_found"] = len(movies) > 0
        if not checks["movies_found"]:
            failures.append("movies_found empty")
    else:
        checks["movies_found"] = True

    unresolved = meta.get("unresolved_titles") or []
    if case.require_unresolved:
        checks["unresolved"] = bool(unresolved) or case.expect_declined
        if case.expect_declined and "resolve_movie" in tools:
            checks["unresolved"] = True
        if not checks["unresolved"]:
            failures.append("expected unresolved_titles")
    else:
        checks["unresolved"] = True

    if case.expect_movies_contain and not case.expect_declined:
        blob = json.dumps(
            {
                "movies_found": movies,
                "recommendations": recs,
                "peer_opinions": peers,
                "compare": meta.get("compare") or [],
            },
            ensure_ascii=False,
        ).lower()
        missing_titles = [t for t in case.expect_movies_contain if t.lower() not in blob]
        # For Se7en / Seven, pass if either token present
        if case.id == "G02":
            missing_titles = [] if ("seven" in blob or "se7en" in blob) else case.expect_movies_contain
        checks["expect_movies_contain"] = not missing_titles
        if missing_titles:
            failures.append(f"expected movies not in metadata: {missing_titles}")
    else:
        checks["expect_movies_contain"] = True

    return {
        "passed": all(checks.values()),
        "checks": checks,
        "failures": failures,
        "tools_used": tools,
    }


def judge_output(case: Case, reply, settings: Settings) -> dict[str, Any]:
    meta = reply.metadata or {}
    evidence = {
        "declined_flag": reply.declined,
        "tools_used": reply.tool_calls,
        "recommendations": meta.get("recommendations") or [],
        "peer_opinions": meta.get("peer_opinions") or [],
        "movies_found": meta.get("movies_found") or [],
        "unresolved_titles": meta.get("unresolved_titles") or [],
        "compare": meta.get("compare") or [],
        "taste_summary": meta.get("taste_summary"),
    }
    llm_kwargs: dict[str, Any] = {
        "model": settings.openai_model,
        "api_key": settings.openai_api_key,
        "temperature": 0,
    }
    if settings.openai_base_url:
        llm_kwargs["base_url"] = settings.openai_base_url
    judge = ChatOpenAI(**llm_kwargs).with_structured_output(JudgeVerdict)

    system = (
        "You are a strict evaluator for a catalogue-grounded movie assistant. "
        "Pass only if the assistant output is consistent with the tool evidence and "
        "matches the task (answer or refuse). Fail if it invents movie titles, ratings, "
        "or peer stats not supported by evidence, or if it answers when it should refuse "
        "(or refuses when it should answer)."
    )
    human = {
        "query": case.query,
        "user_id": case.user_id,
        "expected": case.expected_block(),
        "assistant_message": reply.message,
        "tool_evidence": evidence,
    }
    verdict: JudgeVerdict = judge.invoke(
        [
            SystemMessage(content=system),
            HumanMessage(content=json.dumps(human, ensure_ascii=False)),
        ]
    )
    return verdict.model_dump()


def evaluate_case(case: Case, reply, settings: Settings) -> dict[str, Any]:
    tool_score = score_tools(case, reply)
    judge = judge_output(case, reply, settings)
    passed = bool(tool_score["passed"] and judge.get("passed"))
    return {
        "id": case.id,
        "passed": passed,
        "expected": case.expected_block(),
        "tool_eval": tool_score,
        "output_judge": judge,
        "actual": {
            "declined": reply.declined,
            "used_fallback": reply.used_fallback,
            "tools": reply.tool_calls,
            "message": reply.message,
            "metadata": reply.metadata,
        },
        "notes": case.notes,
        "query": case.query,
        "user_id": case.user_id,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval agent: tools + LLM judge on output")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument("--ids", type=str, default=None)
    args = parser.parse_args(argv)

    settings = get_settings()
    if not settings.has_openai:
        print("OPENAI_API_KEY missing — cannot run agent eval.", file=sys.stderr)
        return 2

    catalog = load_catalog(args.data_dir)
    assistant = MovieAssistant(catalog, settings)

    cases = CASES
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        cases = [c for c in CASES if c.id in wanted]
    if args.limit is not None:
        cases = cases[: args.limit]

    results = []
    for case in cases:
        print(f"Running {case.id} ...", file=sys.stderr)
        reply = assistant.ask(case.user_id, case.query)
        print(f"  judging {case.id} ...", file=sys.stderr)
        results.append(evaluate_case(case, reply, settings))

    n_pass = sum(1 for r in results if r["passed"])
    n_tool = sum(1 for r in results if r["tool_eval"]["passed"])
    n_judge = sum(1 for r in results if r["output_judge"].get("passed"))
    report = {
        "eval": "agent",
        "llm_used": True,
        "model": settings.openai_model,
        "n_cases": len(results),
        "n_passed": n_pass,
        "pass_rate": round(n_pass / len(results), 4) if results else None,
        "tool_pass_rate": round(n_tool / len(results), 4) if results else None,
        "judge_pass_rate": round(n_judge / len(results), 4) if results else None,
        "results": results,
    }
    print_report(report, args.out)
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
