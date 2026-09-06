"""
Load-aware LLM router for Phantom.

Weighted-priority routing with a speed lane: short or streaming calls prefer
Groq (fastest, ~300+ TPS) exclusively; everything else is scored across cloud
providers by weight * (remaining budget fraction), so higher-priority
providers (Gemini) carry the bulk of ordinary traffic while a 15% reserve
buffer keeps every provider from running itself fully dry. Automatic
quarantine on repeated failures; local Ollama is the last-resort fallback
when no cloud slot qualifies. All state is in-memory per process — no
external store.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from utils.usage_logger import log_usage, summarize as _summarize_usage

logger = logging.getLogger(__name__)


def _client_model_name(client: Any) -> str:
    """
    Best-effort model id from a live LangChain client.

    Read off the client rather than duplicating the model strings in a second
    dict — a parallel mapping would silently drift the moment a model name is
    fixed in _get_client() (which has happened repeatedly in this project as
    providers deprecate models).
    """
    for attr in ("model_name", "model"):
        value = getattr(client, attr, None)
        if isinstance(value, str) and value:
            return value
    return "unknown"

# Provider tiers: weight (selection priority), tpm (per-minute token budget —
# already 85% of each provider's real rate limit), and speed_tier (informational;
# only "fast" is currently special-cased, by the speed lane).
PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "gemini":     {"weight": 100, "tpm": 212500, "speed_tier": "medium", "context_limit": 800000},
    "openrouter": {"weight": 40,  "tpm": 17000,  "speed_tier": "medium", "context_limit": 60000},
    "nvidia":     {"weight": 25,  "tpm": 8500,   "speed_tier": "medium", "context_limit": 60000},
    "xai":        {"weight": 25,  "tpm": 8500,   "speed_tier": "medium", "context_limit": 100000},
    "groq":       {"weight": 60,  "tpm": 5100,   "speed_tier": "fast",   "context_limit": 6000},
    "ollama":     {"weight": 1,   "tpm": 999999, "speed_tier": "local",  "context_limit": 4000},
}

# Cloud provider names in PROVIDER_CONFIG's declared order, Ollama excluded —
# it's never a weighted-selection candidate, only the explicit fallback.
CLOUD_PROVIDER_NAMES: list[str] = [n for n in PROVIDER_CONFIG if n != "ollama"]

QUARANTINE_SECONDS = 60.0
WINDOW_SECONDS = 60.0
FAILURE_THRESHOLD = 2

# Speed lane: calls at or under this size (or any streaming call) prefer Groq
# exclusively before weighted selection is even considered.
SPEED_LANE_TOKEN_THRESHOLD = 200

# Reserve buffer: a slot is skipped once its remaining budget drops below this
# fraction of its total limit, so no provider ever gets run fully dry.
RESERVE_FRACTION = 0.15


def _estimate_tokens(text: str) -> int:
    """Rough input-token estimate: word_count * 1.3 + 300 (prompt/overhead)."""
    words = len(text.split())
    return int(words * 1.3 + 300)


def _extract_part_text(part: Any) -> str:
    """
    Pull the text out of one Gemini content part.

    Verified live shape: each part is a plain dict —
    {'type': 'text', 'text': '...', 'extras': {'signature': '<huge base64 blob>'}}
    — NOT an object with a `.text` attribute. Checking dicts first (and
    pulling the 'text' key specifically) matters: falling through to
    str(part) for a dict would stringify the *entire* dict, signature blob
    included, which is not "plain text" by any reasonable definition. The
    `.text`-attribute branch is kept as a defensive fallback in case a
    future SDK version wraps parts in real objects instead of dicts.
    """
    if part is None:
        return ""
    if isinstance(part, dict):
        return str(part.get("text", ""))
    if hasattr(part, "text"):
        return str(part.text)
    return str(part)


def safe_content(response: Any) -> str:
    """
    Always returns a plain string from any LLM response, regardless of
    provider. Prefer this over reading `response.content` directly anywhere
    downstream — Gemini's `.content` is a list of structured parts, not a
    string, and this collapses that shape (or any string content, unchanged)
    into plain text.
    """
    content = getattr(response, "content", "")
    if isinstance(content, list):
        return " ".join(_extract_part_text(part) for part in content if part is not None).strip()
    return str(content) if content else ""


def _normalize_response(response: Any, provider_name: str) -> Any:
    """
    Ensure response.content is always a plain string regardless of provider.

    Only Gemini needs this — every other provider here already returns a
    plain string. Mutates response.content in place and returns the same
    object, so call sites don't need to remember to reassign anything.
    """
    if provider_name == "gemini":
        content = response.content
        if isinstance(content, list):
            response.content = " ".join(
                _extract_part_text(part) for part in content if part is not None
            ).strip()
    return response


@dataclass
class ProviderSlot:
    """
    Per-provider rolling budget, failure count, and lazily-built client.

    weight/limit/speed_tier are properties reading PROVIDER_CONFIG rather than
    stored fields, so PROVIDER_CONFIG stays the single source of truth — no
    risk of a slot drifting out of sync with its own configured tier.
    """

    name: str
    tokens_used: int = 0
    window_start: float = field(default_factory=time.monotonic)
    consecutive_failures: int = 0
    quarantined_until: float = 0.0
    retry_count: int = 0
    next_retry_at: float = 0.0
    client: Any = None

    @property
    def limit(self) -> int:
        return PROVIDER_CONFIG[self.name]["tpm"]

    @property
    def weight(self) -> int:
        return PROVIDER_CONFIG[self.name]["weight"]

    @property
    def speed_tier(self) -> str:
        return PROVIDER_CONFIG[self.name]["speed_tier"]

    @property
    def context_limit(self) -> int:
        return PROVIDER_CONFIG[self.name]["context_limit"]

    def _maybe_reset_window(self) -> None:
        now = time.monotonic()
        if now - self.window_start >= WINDOW_SECONDS:
            self.window_start = now
            self.tokens_used = 0

    def remaining_tokens(self) -> int:
        self._maybe_reset_window()
        return max(0, self.limit - self.tokens_used)

    @property
    def available_tokens(self) -> int:
        return self.remaining_tokens()

    def backoff_seconds(self) -> float:
        """Exponential backoff for this slot's current failure streak, capped at 60s."""
        base = 2.0
        return min(base ** self.retry_count, 60.0)

    def backoff_remaining(self) -> float:
        """Seconds left before this slot may be retried (0.0 if retryable now)."""
        return max(0.0, self.next_retry_at - time.monotonic())

    def is_quarantined(self) -> bool:
        return time.monotonic() < self.quarantined_until

    @property
    def is_healthy(self) -> bool:
        """
        A slot is unhealthy only once it has hit FAILURE_THRESHOLD consecutive
        failures AND its exponential backoff window hasn't elapsed yet. A
        single isolated blip never sidelines a provider.

        Timing uses monotonic (not wall clock) throughout, matching
        quarantined_until/window_start — mixing time.time() with
        time.monotonic() in the same comparisons is a real bug source, since
        a system clock adjustment would corrupt the backoff window.
        """
        if self.consecutive_failures >= FAILURE_THRESHOLD:
            return time.monotonic() >= self.next_retry_at
        return True

    def record_success(self, tokens: int) -> None:
        self._maybe_reset_window()
        self.tokens_used += max(0, tokens)
        self.consecutive_failures = 0
        self.retry_count = 0
        self.next_retry_at = 0.0
        self.quarantined_until = 0.0

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        self.retry_count += 1
        self.next_retry_at = time.monotonic() + self.backoff_seconds()
        if self.consecutive_failures >= FAILURE_THRESHOLD:
            # Kept in sync so is_quarantined() (used elsewhere) never disagrees
            # with is_healthy. consecutive_failures is deliberately NOT reset
            # here any more — is_healthy needs the streak to stay above the
            # threshold for the backoff gate to apply at all.
            self.quarantined_until = self.next_retry_at


class PhantomRouter:
    """
    Weighted-priority router across cloud LLM providers with a Groq speed
    lane and a local Ollama fallback.

    _pick_slot() rules, in order:
      1. Speed lane — stream=True or a small request (<200 est. tokens)
         prefers Groq exclusively if it's healthy and has budget.
      2. Weighted selection — among healthy, keyed, non-reserve-exhausted
         cloud slots with enough remaining budget for this call, picks the
         highest `weight * (available / limit)` score.
      3. Ollama — only when no cloud candidate qualifies at all.
    """

    def __init__(self, api_keys: dict[str, str], ollama_host: str, ollama_model: str):
        self._api_keys = api_keys
        self._ollama_host = ollama_host
        self._ollama_model = ollama_model
        self._slots: dict[str, ProviderSlot] = {
            name: ProviderSlot(name=name) for name in PROVIDER_CONFIG
        }

    @classmethod
    def from_env(cls) -> "PhantomRouter":
        api_keys = {
            "gemini": os.environ.get("GEMINI_API_KEY", ""),
            "openrouter": os.environ.get("OPENROUTER_API_KEY", ""),
            "nvidia": os.environ.get("NVIDIA_API_KEY", ""),
            "xai": os.environ.get("XAI_API_KEY", ""),
            "groq": os.environ.get("GROQ_API_KEY", ""),
        }
        return cls(
            api_keys=api_keys,
            ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            ollama_model=os.environ.get("OLLAMA_MODEL", "llama3:latest"),
        )

    # ── Slot selection ────────────────────────────────────────────────────

    def _pick_slot(
        self,
        estimated_tokens: int,
        stream: bool = False,
        exclude: frozenset[str] = frozenset(),
    ) -> tuple[ProviderSlot, str]:
        """
        Returns (slot, lane), where lane is "speed", "weighted", or "fallback".

        `exclude` is per-call, not persistent state: it's how invoke()/stream()
        cascade through candidates that already failed within THIS call
        without touching the cross-call quarantine counters.
        """
        # 1. Speed lane
        if (stream or estimated_tokens < SPEED_LANE_TOKEN_THRESHOLD) and "groq" not in exclude:
            groq = self._slots["groq"]
            if (
                self._api_keys.get("groq")
                and groq.is_healthy
                and groq.available_tokens >= estimated_tokens
            ):
                self._log_pick(groq, "speed", estimated_tokens)
                return groq, "speed"
            # Groq saturated/unhealthy/keyless — fall through to weighted selection.

        # 2. Weighted selection
        candidates: list[tuple[float, ProviderSlot]] = []
        for name in CLOUD_PROVIDER_NAMES:
            if name in exclude:
                continue
            if not self._api_keys.get(name):
                continue
            slot = self._slots[name]
            if not slot.is_healthy:
                logger.info(
                    "[%s] backing off %.0fs (retry #%d)",
                    slot.name, slot.backoff_remaining(), slot.retry_count,
                )
                continue
            if slot.available_tokens < estimated_tokens:
                continue
            if slot.available_tokens < slot.limit * RESERVE_FRACTION:
                continue  # reserve buffer — never run a slot fully dry
            score = slot.weight * (slot.available_tokens / slot.limit)
            candidates.append((score, slot))

        if candidates:
            candidates.sort(key=lambda pair: pair[0], reverse=True)
            best_score, best_slot = candidates[0]
            self._log_pick(best_slot, "weighted", estimated_tokens, score=best_score)
            return best_slot, "weighted"

        # 3. Ollama fallback — no cloud candidate qualified at all.
        ollama = self._slots["ollama"]
        self._log_pick(ollama, "fallback", estimated_tokens)
        return ollama, "fallback"

    def _log_pick(self, slot: ProviderSlot, lane: str, estimated_tokens: int, score: float | None = None) -> None:
        limit = slot.limit
        available = slot.available_tokens
        pct = (available / limit * 100.0) if limit else 0.0
        if score is None:
            score = slot.weight * (available / limit) if limit else 0.0
        logger.info(
            "[router] -> %s | score=%.2f | weight=%d | remaining=%d/%d (%.0f%%) | lane=%s",
            slot.name, score, slot.weight, available, limit, pct, lane,
        )

    # ── Client construction (lazy, cached per slot for the process lifetime) ──

    def _get_client(self, name: str):
        slot = self._slots[name]
        if slot.client is not None:
            return slot.client

        if name == "groq":
            # llama3-8b-8192 is decommissioned (400 model_decommissioned) —
            # verified live. Same replacement already proven working
            # elsewhere in this codebase (phantom_graph.py).
            from langchain_groq import ChatGroq
            slot.client = ChatGroq(
                model="openai/gpt-oss-120b", api_key=self._api_keys["groq"], temperature=0.3,
            )
        elif name == "gemini":
            # gemini-1.5-flash, -2.0-flash, and -2.5-flash are all 404 now —
            # verified live; Google's error body names the replacement.
            # NOTE: unlike every other provider here, gemini-3.6-flash returns
            # response.content as a list of structured parts (with a
            # 'signature' field), not a plain string. Anything reading
            # .content downstream must handle both shapes.
            from langchain_google_genai import ChatGoogleGenerativeAI
            slot.client = ChatGoogleGenerativeAI(
                model="gemini-3.6-flash", api_key=self._api_keys["gemini"], temperature=0.3,
            )
        elif name == "openrouter":
            # meta-llama/llama-3-8b-instruct:free no longer exists on OpenRouter
            # (404) — verified live against their /models endpoint. This is the
            # same free model phantom_graph.py's fallback chain already uses.
            from langchain_openai import ChatOpenAI
            slot.client = ChatOpenAI(
                model="google/gemma-4-31b-it:free", api_key=self._api_keys["openrouter"],
                base_url="https://openrouter.ai/api/v1", temperature=0.3,
            )
        elif name == "nvidia":
            # meta/llama-3.1-8b-instruct has reached end-of-life (410 Gone) and
            # several other listed NVIDIA NIM models 404 for this account even
            # though /v1/models lists them (per-model access isn't universal).
            # This one was verified to actually respond.
            from langchain_openai import ChatOpenAI
            slot.client = ChatOpenAI(
                model="meta/llama-3.2-11b-vision-instruct", api_key=self._api_keys["nvidia"],
                base_url="https://integrate.api.nvidia.com/v1", temperature=0.3,
            )
        elif name == "xai":
            # Left as-is: the configured XAI_API_KEY itself is rejected
            # ("Incorrect API key provided") independent of model name, so
            # there's nothing to verify a replacement model against yet.
            # grok-beta is also deprecated on xAI's side — once a valid key
            # is in place, check https://api.x.ai/v1/models for the current
            # model id (likely a grok-3/grok-4 variant) before relying on this.
            from langchain_openai import ChatOpenAI
            slot.client = ChatOpenAI(
                model="grok-beta", api_key=self._api_keys["xai"],
                base_url="https://api.x.ai/v1", temperature=0.3,
            )
        elif name == "ollama":
            from langchain_ollama import ChatOllama
            slot.client = ChatOllama(
                model=self._ollama_model, base_url=self._ollama_host, temperature=0.3,
            )
        else:
            raise ValueError(f"Unknown provider: {name}")

        return slot.client

    # ── Shared token-estimate helper ──────────────────────────────────────

    @staticmethod
    def _resolve_estimate(messages: list, estimated_tokens: int | None) -> int:
        """
        Callers may pass an explicit estimate; otherwise it's computed from
        the actual message content (falling back to 500 only if that's not
        possible), rather than always defaulting to a flat 500 regardless of
        real prompt size — that would systematically under-count usage for
        anything longer than a short message.
        """
        if estimated_tokens is not None:
            return estimated_tokens
        try:
            text = "\n".join(str(getattr(m, "content", m)) for m in messages)
            return _estimate_tokens(text) if text else 500
        except Exception:
            return 500

    # ── Public entry points ───────────────────────────────────────────────

    def _log_usage(self, slot: ProviderSlot, client: Any, tokens: int, session_id: str) -> None:
        """Append this call to the persistent usage log (never raises)."""
        try:
            log_usage(
                provider=slot.name,
                model=_client_model_name(client),
                tokens_used=tokens,
                window_tokens=slot.tokens_used,
                window_limit=slot.limit,
                session_id=session_id,
            )
        except Exception:
            pass

    def peek_context_limit(self, estimated_tokens: int = 500, stream: bool = False) -> int:
        """
        Context limit of the slot _pick_slot() would choose right now, without
        committing to it. Lets a caller trim its message list to the provider
        that will actually serve the call.

        Advisory only: a failure cascade inside invoke() can still land on a
        different provider than the one peeked here. Since trimming is
        calibrated to the *smallest* plausible limit in practice (Groq's 6k
        for short/streaming calls), a later switch is to a roomier provider,
        not a tighter one.
        """
        slot, _lane = self._pick_slot(estimated_tokens, stream=stream)
        return slot.context_limit

    def daily_summary(self, hours: float = 24.0) -> dict:
        """
        Usage over the last `hours`, grouped by provider:
        {"gemini": {"calls": 14, "tokens": 8420}, ...}
        """
        return _summarize_usage(hours=hours)

    def invoke(
        self,
        messages: list,
        estimated_tokens: int | None = None,
        stream: bool = False,
        session_id: str = "unknown",
        **kwargs,
    ) -> tuple[Any, str]:
        """
        Invoke the best available provider for this call.

        Returns (ai_message, provider_name_used). On a cloud provider failure,
        the slot's failure count is recorded (quarantining it after 2
        consecutive failures across separate calls) and the router cascades
        to the NEXT-best cloud candidate — not straight to Ollama — so Ollama
        only engages once every cloud option has actually been exhausted for
        this call.
        """
        estimated = self._resolve_estimate(messages, estimated_tokens)

        tried: set[str] = set()
        while True:
            slot, _lane = self._pick_slot(estimated, stream=stream, exclude=frozenset(tried))

            try:
                client = self._get_client(slot.name)
                response = client.invoke(messages, **kwargs)
                response = _normalize_response(response, slot.name)
                slot.record_success(estimated)
                self._log_usage(slot, client, estimated, session_id)
                self.status(slot.name)
                return response, slot.name
            except Exception as exc:
                slot.record_failure()
                if slot.name == "ollama":
                    # Nothing left to fall back to.
                    raise
                logger.warning(
                    "[PhantomRouter] %s failed (%s) - trying next candidate.",
                    slot.name, exc,
                )
                tried.add(slot.name)

    def stream(self, messages: list, estimated_tokens: int | None = None,
               session_id: str = "unknown", **kwargs):
        """
        Streaming variant. Always routes via the speed lane in _pick_slot
        (stream=True), so Groq is preferred whenever it's healthy.

        A failure before the first chunk is yielded cascades through the
        remaining candidates exactly like invoke(). A failure mid-stream
        (after chunks have already reached the caller) cannot be silently
        retried on a different provider without duplicating/confusing output,
        so it propagates as-is once streaming has genuinely started.
        """
        estimated = self._resolve_estimate(messages, estimated_tokens)

        tried: set[str] = set()
        while True:
            slot, _lane = self._pick_slot(estimated, stream=True, exclude=frozenset(tried))
            client = self._get_client(slot.name)

            try:
                chunk_iter = client.stream(messages, **kwargs)
                first_chunk = _normalize_response(next(chunk_iter), slot.name)
            except StopIteration:
                slot.record_success(estimated)
                self._log_usage(slot, client, estimated, session_id)
                self.status(slot.name)
                return
            except Exception as exc:
                slot.record_failure()
                if slot.name == "ollama":
                    raise
                logger.warning(
                    "[PhantomRouter] %s failed to start stream (%s) - trying next candidate.",
                    slot.name, exc,
                )
                tried.add(slot.name)
                continue

            # First chunk succeeded — committed to this slot for the rest of
            # the stream; a failure from here on propagates rather than
            # silently retrying elsewhere.
            yield first_chunk
            try:
                for chunk in chunk_iter:
                    yield _normalize_response(chunk, slot.name)
                slot.record_success(estimated)
                self._log_usage(slot, client, estimated, session_id)
                self.status(slot.name)
            except Exception as exc:
                slot.record_failure()
                logger.warning("[PhantomRouter] %s failed mid-stream (%s).", slot.name, exc)
                raise
            return

    # ── Async entry points ────────────────────────────────────────────────
    # Mirrors of invoke()/stream() using the providers' native async APIs, so
    # one slow call doesn't block the whole process under concurrent load.
    # Selection, normalization, and slot bookkeeping stay synchronous — they
    # are CPU-only and must not interleave mid-decision.

    async def ainvoke(
        self,
        messages: list,
        estimated_tokens: int | None = None,
        stream: bool = False,
        session_id: str = "unknown",
        **kwargs,
    ) -> tuple[Any, str]:
        """Async variant of invoke(), with the same cascade and fallback rules."""
        estimated = self._resolve_estimate(messages, estimated_tokens)

        tried: set[str] = set()
        while True:
            slot, _lane = self._pick_slot(estimated, stream=stream, exclude=frozenset(tried))

            try:
                client = self._get_client(slot.name)
                response = await client.ainvoke(messages, **kwargs)
                response = _normalize_response(response, slot.name)
                slot.record_success(estimated)
                self._log_usage(slot, client, estimated, session_id)
                self.status(slot.name)
                return response, slot.name
            except Exception as exc:
                slot.record_failure()
                if slot.name == "ollama":
                    raise
                logger.warning(
                    "[PhantomRouter] %s failed async (%s) - trying next candidate.",
                    slot.name, exc,
                )
                tried.add(slot.name)

    async def astream(
        self,
        messages: list,
        estimated_tokens: int | None = None,
        session_id: str = "unknown",
        **kwargs,
    ):
        """
        Async streaming variant. Same speed-lane routing and same
        commit-after-first-chunk semantics as the sync stream().
        """
        estimated = self._resolve_estimate(messages, estimated_tokens)

        tried: set[str] = set()
        while True:
            slot, _lane = self._pick_slot(estimated, stream=True, exclude=frozenset(tried))
            client = self._get_client(slot.name)

            started = False
            try:
                agen = client.astream(messages, **kwargs)
                async for chunk in agen:
                    started = True
                    yield _normalize_response(chunk, slot.name)
                slot.record_success(estimated)
                self._log_usage(slot, client, estimated, session_id)
                self.status(slot.name)
                return
            except Exception as exc:
                slot.record_failure()
                if started or slot.name == "ollama":
                    # Already yielded to the caller (or nothing left to try) —
                    # switching providers now would duplicate output.
                    logger.warning("[PhantomRouter] %s failed async stream (%s).", slot.name, exc)
                    raise
                logger.warning(
                    "[PhantomRouter] %s failed to start async stream (%s) - trying next candidate.",
                    slot.name, exc,
                )
                tried.add(slot.name)

    # ── Status / observability ────────────────────────────────────────────

    def status_all(self) -> dict:
        """Window state for every slot, for dashboards/health endpoints."""
        out = {}
        for name, slot in self._slots.items():
            out[name] = {
                "tokens_used": slot.tokens_used,
                "tokens_remaining": slot.remaining_tokens(),
                "limit": slot.limit,
                "weight": slot.weight,
                "speed_tier": slot.speed_tier,
                "context_limit": slot.context_limit,
                "window_age_seconds": round(time.monotonic() - slot.window_start, 1),
                "healthy": slot.is_healthy,
                "consecutive_failures": slot.consecutive_failures,
                "retry_count": slot.retry_count,
                "backoff_remaining_seconds": round(slot.backoff_remaining(), 1),
                "has_key": bool(self._api_keys.get(name)) or name == "ollama",
            }
        return out

    def status(self, provider: str) -> dict:
        """
        Snapshot a slot's routing state and log it. Called automatically at
        the end of every successful invoke()/stream(); safe to call manually
        for diagnostics too.
        """
        slot = self._slots[provider]
        window_age = round(time.monotonic() - slot.window_start, 1)
        info = {
            "provider": provider,
            "tokens_used": slot.tokens_used,
            "tokens_remaining": slot.remaining_tokens(),
            "window_age_seconds": window_age,
        }
        logger.info(
            "[PhantomRouter] provider=%s tokens_used=%d tokens_remaining=%d window_age=%.1fs",
            info["provider"], info["tokens_used"], info["tokens_remaining"], info["window_age_seconds"],
        )
        return info


# ── Process-wide router singleton ─────────────────────────────────────────────
# Slot budgets/backoff live in memory per instance, so anything that wants a
# coherent view (the /status endpoint, background tasks) must share one router
# rather than constructing its own.

_router_singleton: PhantomRouter | None = None


def get_router() -> PhantomRouter:
    """Shared process-wide PhantomRouter, built from the environment once."""
    global _router_singleton
    if _router_singleton is None:
        _router_singleton = PhantomRouter.from_env()
    return _router_singleton
