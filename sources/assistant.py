"""Decline gate + single orchestrator agent (tools, not sub-agents)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openai import APIError, OpenAIError, RateLimitError
from langchain_core.exceptions import LangChainException

from sources.agent import MovieOrchestratorAgent
from sources.catalog import Catalog
from sources.decline import check_user
from sources.fallback import run_fallback
from sources.settings import Settings, get_settings


@dataclass
class AssistantReply:
    intent: str
    declined: bool
    message: str
    tool_calls: list[str] = field(default_factory=list)
    used_fallback: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class MovieAssistant:
    def __init__(self, catalog: Catalog | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.catalog = catalog or Catalog(self.settings.data_dir)

    def ask(self, user_id: int, query: str) -> AssistantReply:
        user_check = check_user(self.catalog, user_id)
        if user_check.declined:
            return AssistantReply(
                intent="decline",
                declined=True,
                message=user_check.message,
                metadata={"user_id": user_id, "reason": "unknown_user"},
            )

        if not self.settings.has_openai:
            intent, declined, message, meta = run_fallback(self.catalog, user_id, query)
            return AssistantReply(
                intent=intent,
                declined=declined,
                message=message + "\n\n[fallback: OPENAI_API_KEY missing]",
                used_fallback=True,
                metadata=meta,
            )

        try:
            agent = MovieOrchestratorAgent(self.catalog, self.settings)
            result = agent.run(user_id, query)
            declined = result.declined
            meta = result.metadata or {}
            # If the agent resolved a required title to "not in catalogue", treat as decline.
            if meta.get("unresolved_titles") and not meta.get("recommendations") and not meta.get(
                "peer_opinions"
            ):
                declined = True
            return AssistantReply(
                intent="agent",
                declined=declined,
                message=result.message,
                tool_calls=result.tool_calls,
                metadata=meta,
            )
        except (RateLimitError, APIError, OpenAIError, LangChainException, Exception) as exc:
            if exc.__class__.__name__ in {"RuntimeError"} and "OPENAI_API_KEY" in str(exc):
                raise
            intent, declined, message, meta = run_fallback(self.catalog, user_id, query)
            return AssistantReply(
                intent=intent,
                declined=declined,
                message=(
                    f"{message}\n\n"
                    f"[fallback: LLM error — {exc.__class__.__name__}]"
                ),
                used_fallback=True,
                metadata=meta,
            )
