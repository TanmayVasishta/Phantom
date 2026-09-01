"""
Conversation buffer — stores the last N turns for multi-turn context resolution.

Prevents "delete that file" from being ambiguous by tracking what was
mentioned in recent turns. Session-scoped only — never persisted.
"""

from __future__ import annotations

import re
import time
from collections import deque

from utils.models import ConversationTurn


# Pronouns/references that trigger resolution
_REFERENCE_PRONOUNS = frozenset({
    "that", "it", "this", "those", "them",
    "the file", "the folder", "the document", "the directory",
})


class ConversationBuffer:
    """
    Stores last N turns of the current session conversation.

    Used for:
    - Pronoun/reference resolution ("delete that" → "delete notes.txt")
    - Multi-turn coherence (inject recent context into enriched prompt)

    Cleared on session end. Max 10 turns to keep prompt size manageable.
    """

    def __init__(self, max_turns: int = 10):
        self._buffer: deque[ConversationTurn] = deque(maxlen=max_turns)

    def add(self, role: str, content: str, intent: str = "") -> None:
        """
        Record a conversation turn. content must already be sanitised (no PII).

        role: "user" | "assistant"
        """
        self._buffer.append(
            ConversationTurn(
                role=role,
                content=content,
                intent=intent,
                timestamp=time.time(),
            )
        )

    def get_recent(self, n: int = 5) -> list[ConversationTurn]:
        """Return the last n turns (most recent last)."""
        turns = list(self._buffer)
        return turns[-n:]

    def format_for_prompt(self, n: int = 5) -> str:
        """
        Format recent turns as a conversation block for prompt injection.
        Returns empty string if buffer is empty.
        """
        turns = self.get_recent(n)
        if not turns:
            return ""
        lines = [f"{t.role.upper()}: {t.content}" for t in turns]
        return "\n".join(lines)

    def resolve_reference(self, query: str) -> str:
        """
        Resolve pronoun references in query using recent conversation context.

        If query contains a reference pronoun (e.g. "delete that"),
        look in the last 3 user turns for a file/path mention and append it.
        Returns the enriched query, or the original query if nothing resolved.
        """
        query_lower = query.lower()
        has_reference = any(p in query_lower for p in _REFERENCE_PRONOUNS)
        if not has_reference:
            return query

        # Look at last 3 user turns for filesystem paths or filenames
        user_turns = [t for t in self.get_recent(3) if t.role == "user"]
        for turn in reversed(user_turns):
            # Match file paths (~/..., /..., or filename.ext patterns)
            paths = re.findall(
                r"[~\/][^\s\'\",]+|[\w\-]+\.\w{2,6}|[\w\-]+ (?:folder|directory|file)",
                turn.content,
            )
            if paths:
                return f"{query} (referring to: {paths[-1]})"

        return query

    def clear(self) -> None:
        """Clear all turns. Call at session end."""
        self._buffer.clear()

    def __len__(self) -> int:
        return len(self._buffer)
