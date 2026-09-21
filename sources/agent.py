"""Single orchestrator agent via LangChain (ChatOpenAI + tools)."""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from sources.agent_tools import ToolBelt
from sources.catalog import Catalog
from sources.settings import Settings, get_settings

SYSTEM_PROMPT = """\
You are a movie assistant for a fixed catalogue (MovieLens subset).
The user is identified by userId; personalisation MUST come from rating history tools, not guesswork.

Rules:
- Call tools before answering. Prefer multiple lookups when the question needs them.
- If resolve_movie returns found=false, refuse: the title is outside the catalogue.
- Never invent movie titles, movie_ids, rating numbers, or genre preferences that are \
not present in tool results. Only use tool results.
- For "what should I watch" → get_taste_summary + collaborative_recommend.
- For "people with taste like mine think of X" → resolve_movie(X) → find_similar_users(movie_id=X) \
→ get_movie_ratings_summary(movie_id=X, among_similar_users=true).
- For "like X" / "similar to X" → resolve_movie(X) → collaborative_recommend(like_movie_id=X's id). \
Present the returned recommendations as similar to X. Explain similarity using shared genres \
(and why fields) from the tool payloads. Do NOT say the list is unrelated to X or only based on \
general taste if the tool returned seed-similarity reasons.
- For "why might I like X" / explain fit → resolve_movie(X) + get_taste_summary \
(and optionally get_movie_ratings_summary / find_similar_users). Explain ONLY with:
  (1) genres that appear on BOTH the movie payload and the taste summary / high-rated genres, and/or
  (2) peer or catalogue rating stats from tools.
  Do not invent extra tastes (e.g. "you like mystery") unless those words appear in tool output.
  If overlap is weak, say so briefly using the tool evidence you have.
- For "A or B / compare" → resolve both → compare_movies_for_user.
- Answer in clear concise English unless the user wrote Vietnamese, then answer in Vietnamese.
- If evidence is insufficient, say so and decline rather than guessing.
"""


@dataclass
class AgentResult:
    message: str
    declined: bool
    tool_calls: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class MovieOrchestratorAgent:
    def __init__(
        self,
        catalog: Catalog,
        settings: Settings | None = None,
        *,
        max_rounds: int = 8,
    ):
        self.catalog = catalog
        self.settings = settings or get_settings()
        self.max_rounds = max_rounds
        if not self.settings.has_openai:
            raise RuntimeError(
                "OPENAI_API_KEY is missing. Set it in .env (see .env.example)."
            )

        llm_kwargs: dict = {
            "model": self.settings.openai_model,
            "api_key": self.settings.openai_api_key,
            "temperature": 0,
        }
        if self.settings.openai_base_url:
            llm_kwargs["base_url"] = self.settings.openai_base_url
        self.llm = ChatOpenAI(**llm_kwargs)

    def run(self, user_id: int, query: str) -> AgentResult:
        belt = ToolBelt(self.catalog, user_id)
        tools = belt.as_langchain_tools()
        tool_map = {t.name: t for t in tools}
        llm = self.llm.bind_tools(tools)

        messages: list = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"userId={user_id}\nQuestion: {query}"),
        ]
        used_tools: list[str] = []

        for _ in range(self.max_rounds):
            ai: AIMessage = llm.invoke(messages)
            messages.append(ai)

            if not ai.tool_calls:
                text = (ai.content or "").strip()
                if isinstance(text, list):
                    # rare content-block shape
                    text = "".join(
                        block.get("text", "") if isinstance(block, dict) else str(block)
                        for block in text
                    ).strip()
                return AgentResult(
                    message=str(text),
                    declined=self._looks_declined(str(text), used_tools),
                    tool_calls=used_tools,
                    metadata=belt.metadata(),
                )

            for call in ai.tool_calls:
                name = call["name"]
                args = call.get("args") or {}
                call_id = call["id"]
                used_tools.append(name)
                tool = tool_map.get(name)
                if tool is None:
                    payload = f'{{"error": "unknown tool: {name}"}}'
                else:
                    try:
                        payload = tool.invoke(args)
                    except Exception as exc:  # noqa: BLE001
                        payload = f'{{"error": "{exc}"}}'
                if not isinstance(payload, str):
                    import json

                    payload = json.dumps(payload, ensure_ascii=False)
                messages.append(ToolMessage(content=payload, tool_call_id=call_id))

        return AgentResult(
            message="I could not finish the lookup within the tool-call budget. Please rephrase.",
            declined=True,
            tool_calls=used_tools,
            metadata=belt.metadata(),
        )

    @staticmethod
    def _looks_declined(text: str, used_tools: list[str]) -> bool:
        lower = text.lower()
        markers = (
            "not in",
            "not found",
            "outside the catalogue",
            "outside the catalog",
            "cannot",
            "can't",
            "unable",
            "no rating",
            "insufficient",
            "không có",
            "không tìm",
            "từ chối",
        )
        if any(m in lower for m in markers):
            return True
        if not used_tools and len(text) < 40:
            return True
        return False
