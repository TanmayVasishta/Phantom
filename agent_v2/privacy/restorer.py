"""
Post-LLM response restoration.

Swaps surrogates back to the real values so the user reads a natural answer.
This output is UI-only: it is never logged, never stored, never sent anywhere.
"""
from __future__ import annotations

import re


def _replace_ci(haystack: str, needle: str, replacement: str) -> str:
    """Case-insensitive literal replace."""
    if not needle:
        return haystack
    return re.sub(re.escape(needle), lambda _: replacement, haystack, flags=re.IGNORECASE)


def restore(response: str, pairs: dict[str, str]) -> tuple[str, int]:
    """
    Replace every surrogate in `response` with its original.

    `pairs` is surrogate -> original. Returns (restored_text, replacements_made).

    Longest surrogates go first so a full name is restored before its own
    first-name fragment is considered — replacing "Michael" first would leave
    a mangled "Tanmay Chen" behind.
    """
    if not response or not pairs:
        return response, 0

    restored = response
    count = 0

    for surrogate in sorted(pairs, key=len, reverse=True):
        original = pairs[surrogate]
        if not surrogate:
            continue
        occurrences = len(re.findall(re.escape(surrogate), restored, flags=re.IGNORECASE))
        if occurrences:
            restored = _replace_ci(restored, surrogate, original)
            count += occurrences

    # Partial name handling: the model may refer to "Michael" or "Chen" alone.
    # Only applied to multi-word surrogates whose original is also multi-word,
    # and each part is matched on a word boundary so short fragments don't
    # corrupt unrelated words.
    for surrogate in sorted(pairs, key=len, reverse=True):
        original = pairs[surrogate]
        s_parts = surrogate.split()
        o_parts = original.split()
        if len(s_parts) < 2 or len(o_parts) < 2:
            continue
        for s_part, o_part in zip(s_parts, o_parts):
            if len(s_part) < 3:
                continue
            pattern = re.compile(rf"\b{re.escape(s_part)}\b", re.IGNORECASE)
            found = len(pattern.findall(restored))
            if found:
                restored = pattern.sub(lambda _: o_part, restored)
                count += found

    return restored, count
