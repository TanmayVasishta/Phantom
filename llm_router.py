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
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from utils.usage_logger import log_usage, summarize as _summarize_usage

logger = logging.getLogger(__name__)

# Every provider call below is bounded from the CALLING side, not just via
# each client's own timeout field — verified live (phantom_graph.py's
# equivalent fix, same finding): ChatGroq's request_timeout is genuinely
# honored (a 0.001s setting raised in 1.855s), but ChatGoogleGenerativeAI's
# timeout= is NOT reliably honored for a stalled connection (the same
# 0.001s setting took 34.183s, stuck in the TLS handshake specifically).
# Persistent pool, not a per-call `with` — exiting `with
# ThreadPoolExecutor(...)` blocks on shutdown(wait=True) regardless of any
# timeout already given up on, which would defeat the entire point.
CLOUD_CALL_TIMEOUT_SECONDS = 15
_CALL_EXECUTOR = ThreadPoolExecutor(max_workers=6, thread_name_prefix="phantom-router-call")


def _call_with_timeout(fn: Callable[[], Any], timeout: float = CLOUD_CALL_TIMEOUT_SECONDS) -> Any:
    """Run fn() with a hard deadline enforced here, independent of whether
    the client's own timeout parameter actually works for this provider."""
    future = _CALL_EXECUTOR.submit(fn)
    return future.result(timeout=timeout)


def _client_model_name(client: Any) -> str:
    """
    Best-effort model id from a live LangChain client.

    Read off the client rather than duplicating the model strings in a second
    dict — a parallel mapping would silently drift the moment a model name is
    fixed in _get_client() (which has happened repeatedly in this project as
    providers deprecate models).

    bind_tools() wraps the model in a RunnableBinding, whose model_name/model
    live on .bound rather than the wrapper itself — checked first so a
    tool-bound call (see PhantomRouter._client_for) doesn't silently log
    "unknown" for every model.
    """
    target = getattr(client, "bound", client)
    for attr in ("model_name", "model"):
        value = getattr(target, attr, None)
        if isinstance(value, str) and value:
            return value
    return "unknown"

# Provider tiers: weight (selection priority), tpm (per-minute token budget —
# already 85% of each provider's real rate limit), and speed_tier (informational;
# only "fast" is currently special-cased, by the speed lane).
# agentic_weight is a SEPARATE priority ranking, used only when the caller
# marks a request agentic=True: multi-step file/agent tasks aren't chasing
# interactive chat latency the way normal streaming replies are, so they skip
# the speed lane entirely (see _pick_slot) and are scored on this column
# instead of weight — Gemini's large context and reliability matter more here
# than Groq's raw tokens/sec.
PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "gemini":     {"weight": 100, "agentic_weight": 150, "tpm": 212500, "speed_tier": "medium", "context_limit": 800000},
    "openrouter": {"weight": 40,  "agentic_weight": 80,  "tpm": 17000,  "speed_tier": "medium", "context_limit": 60000},
    "nvidia":     {"weight": 25,  "agentic_weight": 60,  "tpm": 8500,   "speed_tier": "medium", "context_limit": 60000},
    "xai":        {"weight": 25,  "agentic_weight": 40,  "tpm": 8500,   "speed_tier": "medium", "context_limit": 100000},
    "groq":       {"weight": 60,  "agentic_weight": 20,  "tpm": 5100,   "speed_tier": "fast",   "context_limit": 6000},
    "ollama":     {"weight": 1,   "agentic_weight": 5,   "tpm": 999999, "speed_tier": "local",  "context_limit": 4000},
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
    def agentic_weight(self) -> int:
        return PROVIDER_CONFIG[self.name]["agentic_weight"]

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
        agentic: bool = False,
    ) -> tuple[ProviderSlot, str]:
        """
        Returns (slot, lane), where lane is "speed", "weighted", or "fallback".

        `exclude` is per-call, not persistent state: it's how invoke()/stream()
        cascade through candidates that already failed within THIS call
        without touching the cross-call quarantine counters.

        `agentic` skips the speed lane unconditionally, even for a streaming
        call: a multi-step file/agent task isn't chasing chat latency, and
        scores weighted selection on agentic_weight instead of weight —
        Gemini's context/reliability matters more there than Groq's tokens/sec.
        """
        # 1. Speed lane — never for an agentic call.
        if not agentic and (stream or estimated_tokens < SPEED_LANE_TOKEN_THRESHOLD) and "groq" not in exclude:
            groq = self._slots["groq"]
            if (
                self._api_keys.get("groq")
                and groq.is_healthy
                and groq.available_tokens >= estimated_tokens
            ):
                self._log_pick(groq, "speed", estimated_tokens, agentic=agentic)
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
            rank = slot.agentic_weight if agentic else slot.weight
            score = rank * (slot.available_tokens / slot.limit)
            candidates.append((score, slot))

        if candidates:
            candidates.sort(key=lambda pair: pair[0], reverse=True)
            best_score, best_slot = candidates[0]
            self._log_pick(best_slot, "weighted", estimated_tokens, score=best_score, agentic=agentic)
            return best_slot, "weighted"

        # 3. Ollama fallback — no cloud candidate qualified at all.
        ollama = self._slots["ollama"]
        self._log_pick(ollama, "fallback", estimated_tokens, agentic=agentic)
        return ollama, "fallback"

    def _log_pick(self, slot: ProviderSlot, lane: str, estimated_tokens: int,
                  score: float | None = None, agentic: bool = False) -> None:
        limit = slot.limit
        available = slot.available_tokens
        pct = (available / limit * 100.0) if limit else 0.0
        rank = slot.agentic_weight if agentic else slot.weight
        if score is None:
            score = rank * (available / limit) if limit else 0.0
        logger.info(
            "[PhantomRouter] -> %s | tokens: %d/%d | weight=%d | remaining=%d/%d (%.0f%%) | "
            "lane=%s | agentic=%s",
            slot.name, slot.tokens_used, limit, rank, available, limit, pct, lane, agentic,
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
                request_timeout=CLOUD_CALL_TIMEOUT_SECONDS,
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
                timeout=CLOUD_CALL_TIMEOUT_SECONDS,
            )
        elif name == "openrouter":
            # meta-llama/llama-3-8b-instruct:free no longer exists on OpenRouter
            # (404) — verified live against their /models endpoint. This is the
            # same free model phantom_graph.py's fallback chain already uses.
            from langchain_openai import ChatOpenAI
            slot.client = ChatOpenAI(
                model="google/gemma-4-31b-it:free", api_key=self._api_keys["openrouter"],
                base_url="https://openrouter.ai/api/v1", temperature=0.3,
                request_timeout=CLOUD_CALL_TIMEOUT_SECONDS,
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
                request_timeout=CLOUD_CALL_TIMEOUT_SECONDS,
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
                request_timeout=CLOUD_CALL_TIMEOUT_SECONDS,
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

    def _client_for(self, name: str, tools: list | None):
        """
        The slot's cached raw client, tool-bound for this call if `tools` is
        given.

        Binding produces a new wrapper rather than mutating the cached
        client in place, so re-binding per call never disturbs what's
        cached on the slot — it's a cheap local wrap, not a network call,
        and every provider's LangChain client supports it uniformly,
        including Ollama.
        """
        client = self._get_client(name)
        return client.bind_tools(tools) if tools else client

    def invoke(
        self,
        messages: list,
        estimated_tokens: int | None = None,
        stream: bool = False,
        session_id: str = "unknown",
        agentic: bool = False,
        tools: list | None = None,
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

        `agentic=True` skips the speed lane and scores candidates on
        agentic_weight instead of weight — see _pick_slot. `tools`, if
        given, is bound onto whichever client is selected — every client
        _get_client() builds is otherwise plain/tool-less, and a caller
        whose whole ReAct loop depends on tool calls (phantom_graph.py's
        llm_call_node) would silently lose that ability without this.
        """
        estimated = self._resolve_estimate(messages, estimated_tokens)

        tried: set[str] = set()
        while True:
            slot, _lane = self._pick_slot(estimated, stream=stream, exclude=frozenset(tried), agentic=agentic)

            try:
                client = self._client_for(slot.name, tools)
                # Bounded from the calling side — see CLOUD_CALL_TIMEOUT_SECONDS's
                # docstring for why the client's own timeout field alone isn't
                # trustworthy for every provider.
                response = _call_with_timeout(lambda: client.invoke(messages, **kwargs))
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
               session_id: str = "unknown", agentic: bool = False,
               on_provider: Callable[[str], None] | None = None,
               tools: list | None = None, **kwargs):
        """
        Streaming variant. Routes via the speed lane in _pick_slot (stream=
        True) unless agentic=True, so Groq is preferred whenever it's
        healthy for ordinary chat-style calls, while a multi-step agent task
        skips straight to weighted (agentic_weight) selection instead.

        `on_provider`, if given, fires exactly once — right when the router
        commits to a slot, before the first chunk is yielded — so a caller
        that needs to know which provider is serving this response (for a
        UI badge, logging, ...) doesn't have to guess from the chunks
        themselves. Mirrors this codebase's existing token_callback idiom
        rather than inventing a new way to thread information out of a
        generator.

        `tools`, if given, is bound onto whichever client is selected — same
        reasoning as invoke()'s `tools` param: phantom_graph.py's
        llm_call_node ReAct loop needs tool-bound models, and every client
        _get_client() builds is otherwise plain/tool-less.

        A failure before the first chunk is yielded cascades through the
        remaining candidates exactly like invoke(). A failure mid-stream
        (after chunks have already reached the caller) cannot be silently
        retried on a different provider without duplicating/confusing output,
        so it propagates as-is once streaming has genuinely started. Only
        getting to the FIRST chunk is wrapped in the calling-side timeout —
        once a provider is confirmed responsive and chunks are already
        flowing, capping total stream duration would risk truncating a
        long-but-healthy response; the highest-risk moment is the initial
        connection, which is exactly what this bounds.

        That wrapped window covers client.stream(...) itself, not just the
        next() after it — verified live against an unreachable Ollama host:
        client.stream(...) can block on its own well past this timeout
        (the connection attempt happens before any generator is even handed
        back), so wrapping only next(chunk_iter) left that call free to hang
        for however long the underlying HTTP client takes, bypassing this
        backstop entirely and falling through to whatever outer ceiling the
        caller happens to have (60s in phantom_graph.py's run_query — 4x
        this timeout, for exactly the failure class this exists to bound).
        """
        estimated = self._resolve_estimate(messages, estimated_tokens)

        tried: set[str] = set()
        while True:
            slot, _lane = self._pick_slot(estimated, stream=True, exclude=frozenset(tried), agentic=agentic)
            client = self._client_for(slot.name, tools)

            def _start_stream():
                it = client.stream(messages, **kwargs)
                return it, next(it)

            try:
                chunk_iter, first_chunk_raw = _call_with_timeout(_start_stream)
                first_chunk = _normalize_response(first_chunk_raw, slot.name)
            except StopIteration:
                slot.record_success(estimated)
                self._log_usage(slot, client, estimated, session_id)
                self.status(slot.name)
                if on_provider:
                    on_provider(slot.name)
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
            if on_provider:
                on_provider(slot.name)
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
_router_lock = threading.Lock()


def get_router() -> PhantomRouter:
    """
    Shared process-wide PhantomRouter, built from the environment once.

    Double-checked locking: llm_call_node now calls this on every turn (it
    previously never did, so this raced on nobody — see phantom_graph.py's
    llm_call_node docs), and LangGraph turns can run concurrently. The plain
    "if None: construct" this replaced is the same non-atomic-singleton
    pattern already found and fixed for every ChromaDB getter in this
    project (memory/chroma_manager.py) — two threads both observing None
    and each constructing their own PhantomRouter would silently split the
    tracked token budgets this whole feature exists to keep coherent.
    """
    global _router_singleton
    if _router_singleton is None:
        with _router_lock:
            if _router_singleton is None:
                _router_singleton = PhantomRouter.from_env()
    return _router_singleton
