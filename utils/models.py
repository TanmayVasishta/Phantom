"""All Pydantic data models for Project PHANTOM."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class IntentType(str, Enum):
    FILE_OP = "FILE_OP"
    SYSTEM_CMD = "SYSTEM_CMD"
    CALENDAR_OP = "CALENDAR_OP"
    MEMORY_LOOKUP = "MEMORY_LOOKUP"
    WEB_QUERY = "WEB_QUERY"
    GENERAL_QA = "GENERAL_QA"
    UNKNOWN = "UNKNOWN"


class SentinelResult(BaseModel):
    """Output from the Sentinel Node intent classification pass."""

    intent: IntentType = IntentType.UNKNOWN
    sub_intent: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    entities: list[str] = Field(default_factory=list)

    @field_validator("intent", mode="before")
    @classmethod
    def normalise_intent(cls, v: str) -> str:
        valid = {e.value for e in IntentType}
        upper = str(v).upper()
        return upper if upper in valid else "UNKNOWN"

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


class ClarificationRequest(BaseModel):
    """Returned by Sentinel when confidence < threshold."""

    original_query: str
    interpretation: str  # Sentinel's best guess at what the user meant
    confidence: float


class PIIEntity(BaseModel):
    """A single detected PII entity."""

    placeholder: str        # e.g. "[PII_PERSON_1]"
    original_value: str     # actual PII value — kept in RAM, never persisted
    entity_type: str        # e.g. "PERSON", "EMAIL", "AADHAAR"
    tier_detected: int      # 1, 2, or 3
    presidio_score: float = 0.0  # 0.0–1.0; 0.0 if detected by regex (tier 1)
    start: int = 0
    end: int = 0


class RouteDecision(BaseModel):
    """Routing outcome from the Task Orchestrator."""

    target: str             # "local" | "cloud" | "memory"
    risk_score: int = Field(default=0, ge=0, le=100)
    hitl_required: bool = False
    from_cache: bool = False
    enriched_prompt: str = ""


class ExecutionResult(BaseModel):
    """Result of an OS middleware command execution."""

    status: str             # "success" | "error" | "blocked" | "dry_run"
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    command: str = ""
    dry_run_description: str = ""
    filesystem_diff: dict = Field(default_factory=dict)


class HITLDisplayData(BaseModel):
    """Data passed to the HITL approval dialog widget."""

    proposed_action: str
    risk_score: int = Field(ge=0, le=100)
    risk_level: str         # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    risk_color: str         # hex colour string
    memory_context: list[str] = Field(default_factory=list)
    command_preview: str = ""
    timeout_seconds: Optional[int] = None


class ConversationTurn(BaseModel):
    """A single turn in the conversation buffer."""

    role: str               # "user" | "assistant"
    content: str            # sanitised content only — no PII
    intent: str = ""
    timestamp: float = 0.0


class AnnotatedQuery(BaseModel):
    """Query with metadata attached by the PromptIntentAnnotator."""

    raw_text: str
    sanitised_text: str = ""
    input_modality: str     # "voice" | "text"
    language: str = "en"
    language_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    system_state: dict = Field(default_factory=dict)
