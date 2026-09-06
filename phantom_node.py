"""
LangGraph-compatible node wrapping PhantomRouter.

PhantomNode is a callable: it takes {"messages": [...]} and returns
{"messages": [AIMessage(...)]}, so it can be dropped straight into a
StateGraph with graph.add_node("llm", PhantomNode()).

Sync (__call__) and async (acall) variants both exist; the sync contract is
unchanged.
"""

from __future__ import annotations

from llm_router import PhantomRouter
from utils.context_trimmer import trim_messages


class PhantomNode:
    """Callable LangGraph node. Builds its router from the environment once."""

    def __init__(self, router: PhantomRouter | None = None):
        self._router = router or PhantomRouter.from_env()

    def _prepare(self, state: dict) -> tuple[list, str]:
        """
        Trim messages to the context limit of the provider that will actually
        serve this call, and pull the session id for the usage log.
        """
        messages = state.get("messages", [])
        session_id = state.get("session_id") or "unknown"
        if not messages:
            return messages, session_id

        try:
            limit = self._router.peek_context_limit()
            messages = trim_messages(messages, max_tokens=limit)
        except Exception:
            # Trimming is a safeguard, never a hard dependency — an oversized
            # prompt failing at the provider is still better than the node
            # itself dying here.
            pass

        return messages, session_id

    def __call__(self, state: dict) -> dict:
        messages, session_id = self._prepare(state)
        ai_message, _provider_used = self._router.invoke(messages, session_id=session_id)
        return {"messages": [ai_message]}

    async def acall(self, state: dict) -> dict:
        """Async variant of __call__ with the identical contract."""
        messages, session_id = self._prepare(state)
        ai_message, _provider_used = await self._router.ainvoke(messages, session_id=session_id)
        return {"messages": [ai_message]}
