"""
Prompt-injection guard.

Runs on raw user input before anything reaches the LLM. Pattern-based, not
model-based: it must be fast, deterministic, and impossible to talk out of.

This is a blunt instrument by design — it catches the well-known override
phrasings. It is NOT a complete defense (no regex list is), and it carries
real false-positive risk on legitimate roleplay-ish requests; see
check_injection()'s notes.
"""

from __future__ import annotations

import re

# (compiled pattern, human-readable reason)
INJECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ignore (all )?(previous|prior|above) instructions?", re.I),
     "instruction-override attempt ('ignore previous instructions')"),
    (re.compile(r"you are now (a |an )?\w+", re.I),
     "identity-reassignment attempt ('you are now ...')"),
    (re.compile(r"disregard (your )?(system|previous|prior)", re.I),
     "system-prompt disregard attempt"),
    (re.compile(r"pretend (you are|to be)", re.I),
     "persona-injection attempt ('pretend you are ...')"),
    # Narrowed from the original blanket r"(act|behave) as (if )?(?:you are )?(a |an )?\w+",
    # which blocked ordinary role framing like "act as a code reviewer for this
    # file". Role framing is a normal, useful way to ask for work; what actually
    # signals an attack is pairing it with a constraint-removal or a known
    # jailbreak persona. These three patterns target that shape specifically.
    (re.compile(
        r"(act|behave|roleplay|role-play) as (if )?(?:you(?:'re| are)? )?"
        r"(a |an |the )?(dan\b|jailbroken|jail-broken|unrestricted|unfiltered|uncensored|"
        r"unbound|unchained|lawless|amoral|evil|rogue|malicious|godmode|god-mode|"
        r"developer mode|do anything now)", re.I),
     "persona-injection attempt (jailbreak persona)"),
    (re.compile(
        r"(act|behave|pretend|respond) as if you "
        r"(are not|aren't|were not|weren't|have no|had no|don'?t have|do not have|"
        r"has no|no longer have)\b", re.I),
     "persona-injection attempt (constraint removal)"),
    (re.compile(
        r"(act|behave|roleplay|role-play) as (a |an |the )?[\w\s-]{0,30}?\b"
        r"(with|that has|having|who has) no (restrictions?|filters?|limits?|rules?|"
        r"guardrails?|boundaries|ethics|morals)", re.I),
     "persona-injection attempt (restriction-free persona)"),
    (re.compile(r"jailbreak", re.I),
     "explicit jailbreak reference"),
    (re.compile(r"do anything now", re.I),
     "DAN-style jailbreak phrasing"),
    (re.compile(r"\[INST\]|\[/INST\]", re.I),
     "raw instruction tokens in input"),
]


def check_injection(text: str) -> tuple[bool, str]:
    """
    Returns (is_safe, reason).

    is_safe=True  -> reason is ""
    is_safe=False -> reason names which pattern tripped

    The 'act as ...' patterns were deliberately narrowed to jailbreak personas
    and constraint removal, so ordinary role framing ("act as a code reviewer
    for this file") passes. Verified against the full graph, not just this
    function. Remaining false-positive risk sits with the broader patterns
    above ('you are now ...', 'pretend you are ...').
    """
    if not text or not isinstance(text, str):
        return True, ""

    for pattern, reason in INJECTION_PATTERNS:
        if pattern.search(text):
            return False, reason

    return True, ""
