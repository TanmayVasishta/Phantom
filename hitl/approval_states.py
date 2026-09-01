"""HITL approval state enum."""

from enum import Enum


class HITLState(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    TIMEOUT_REJECTED = "timeout_rejected"
    AUTO_APPROVED = "auto_approved"
