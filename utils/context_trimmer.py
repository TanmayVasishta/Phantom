"""
Context-window trimming.

Long conversations grow unbounded; providers then either silently truncate
or throw a context-length error. This trims oldest-first to fit a budget,
always preserving the system prompt and the current user turn.
"""

from __future__ import annotations

from typing import Any

# Words -> tokens multiplier (matches the spec; deliberately conservative,
# real tokenizers average ~1.3x for English prose).
TOKENS_PER_WORD = 1.4

TRIM_NOTICE = "Note: earlier conversation history was trimmed to fit context window."


def _content_text(msg: Any) -> str:
    """
    Message content as plain text.

    Gemini responses carry `.content` as a list of structured parts, so a bare
    str() would count the whole dict repr (signature blobs included) and wildly
    over-estimate. Pull the text out of those parts instead.
    """
    content = getattr(msg, "content", msg)
    if isinstance(content, list):
        parts = []
        for part in content:
            if part is None:
                continue
            if isinstance(part, dict):
                parts.append(str(part.get("text", "")))
            elif hasattr(part, "text"):
                parts.append(str(part.text))
            else:
                parts.append(str(part))
        return " ".join(parts)
    return str(content) if content is not None else ""


def estimate_message_tokens(msg: Any) -> int:
    """Rough token estimate for a single message."""
    return int(len(_content_text(msg).split()) * TOKENS_PER_WORD)


def _is_type(msg: Any, type_name: str) -> bool:
    """True if msg is a LangChain message of the given type ('system'/'human')."""
    if getattr(msg, "type", None) == type_name:
        return True
    return type(msg).__name__.lower().startswith(type_name)


def trim_messages(messages: list, max_tokens: int = 6000) -> list:
    """
    Trim a message list to fit `max_tokens`, oldest dropped first.

    Always preserved:
      - the leading SystemMessage (if index 0 is one)
      - the most recent HumanMessage (the turn actually being answered)

    If anything was dropped, a SystemMessage notice is prepended so the model
    knows history is incomplete rather than silently reasoning over a gap.
    """
    if not messages:
        return []

    system_msg = messages[0] if _is_type(messages[0], "system") else None
    body = messages[1:] if system_msg is not None else list(messages)

    budget = max_tokens
    if system_msg is not None:
        budget -= estimate_message_tokens(system_msg)

    # The newest human turn is non-negotiable — reserve its budget first so it
    # can never be the thing that gets dropped.
    last_human_idx = None
    for i in range(len(body) - 1, -1, -1):
        if _is_type(body[i], "human"):
            last_human_idx = i
            break

    kept_idx: set[int] = set()
    if last_human_idx is not None:
        kept_idx.add(last_human_idx)
        budget -= estimate_message_tokens(body[last_human_idx])

    # Walk newest -> oldest, keeping what fits.
    for i in range(len(body) - 1, -1, -1):
        if i in kept_idx:
            continue
        cost = estimate_message_tokens(body[i])
        if budget - cost < 0:
            continue  # too big; keep scanning, an older/smaller one may still fit
        budget -= cost
        kept_idx.add(i)

    kept = [body[i] for i in sorted(kept_idx)]
    trimmed = len(kept) < len(body)

    result: list = []
    if system_msg is not None:
        result.append(system_msg)
    if trimmed:
        try:
            from langchain_core.messages import SystemMessage
            result.append(SystemMessage(content=TRIM_NOTICE))
        except ImportError:
            pass
    result.extend(kept)
    return result
