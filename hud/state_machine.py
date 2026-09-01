"""
HUD state machine — defines and enforces valid state transitions.

Varshitha's module.

States:
  IDLE → LISTENING → PROCESSING → AWAITING_SENTINEL
       → AWAITING_HITL → DISPLAYING → IDLE
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class HUDState(Enum):
    IDLE = "idle"
    LISTENING = "listening"               # mic active, capturing audio
    PROCESSING = "processing"             # Whisper ASR running
    AWAITING_SENTINEL = "awaiting_sentinel"  # Sentinel + PII processing
    AWAITING_HITL = "awaiting_hitl"       # HITL approval dialog shown
    DISPLAYING = "displaying"             # response shown to user
    ERROR = "error"                       # pipeline error occurred


# Valid transitions: current → {set of allowed next states}
_TRANSITIONS: dict[HUDState, set[HUDState]] = {
    HUDState.IDLE:               {HUDState.LISTENING, HUDState.AWAITING_SENTINEL},
    HUDState.LISTENING:          {HUDState.PROCESSING, HUDState.IDLE, HUDState.ERROR},
    HUDState.PROCESSING:         {HUDState.AWAITING_SENTINEL, HUDState.IDLE, HUDState.ERROR},
    HUDState.AWAITING_SENTINEL:  {HUDState.AWAITING_HITL, HUDState.DISPLAYING, HUDState.IDLE, HUDState.ERROR},
    HUDState.AWAITING_HITL:      {HUDState.DISPLAYING, HUDState.AWAITING_SENTINEL, HUDState.IDLE},
    HUDState.DISPLAYING:         {HUDState.IDLE},
    HUDState.ERROR:              {HUDState.IDLE},
}


class HUDStateMachine:
    """
    Enforces valid state transitions for the Voice HUD.

    The HUD should call transition() on every state change.
    Invalid transitions are logged and rejected (state unchanged).
    """

    def __init__(self):
        self._state = HUDState.IDLE
        self._listeners: list = []  # callables(old_state, new_state)

    @property
    def state(self) -> HUDState:
        return self._state

    def transition(self, new_state: HUDState) -> bool:
        """
        Attempt to transition to new_state.
        Returns True if transition was valid and applied, False otherwise.
        """
        allowed = _TRANSITIONS.get(self._state, set())
        if new_state not in allowed:
            logger.warning(
                f"Invalid HUD transition: {self._state.value} → {new_state.value}"
            )
            return False

        old_state = self._state
        self._state = new_state

        for listener in self._listeners:
            try:
                listener(old_state, new_state)
            except Exception as e:
                logger.error(f"State listener error: {e}")

        return True

    def on_state_change(self, callback) -> None:
        """Register a callback(old_state, new_state) for state change events."""
        self._listeners.append(callback)

    def reset(self) -> None:
        """Force reset to IDLE (use only for error recovery)."""
        old = self._state
        self._state = HUDState.IDLE
        for listener in self._listeners:
            try:
                listener(old, HUDState.IDLE)
            except Exception:
                pass
