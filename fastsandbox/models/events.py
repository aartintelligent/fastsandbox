"""Events published by the daemon."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from ._base import Model

__all__ = ["DaemonEvent", "EventKind"]


class EventKind(Enum):
    """The families of daemon events the library tells apart."""

    SYNC = "sync"
    SANDBOX_LIFECYCLE = "sandbox.lifecycle"
    SANDBOX_PORTS = "sandbox.ports"
    POLICY_NETWORK = "policy.network"
    OTHER = "other"


class DaemonEvent(Model):
    """An event published by the daemon.

    Attributes:
        id: Unique event identifier.
        event_type: Event family, e.g. `sandbox.lifecycle`.
        action: What happened, e.g. `created`, `started`, `published`.
        timestamp: Emission time (RFC 3339).
        sandbox_name: Sandbox the event refers to, if any.
        sandbox_id: Identifier of that sandbox, if any.
        seq: Per-sandbox sequence number, if any.
        data: Event-specific payload.
    """

    id: str
    event_type: str = Field(alias="type")
    action: str
    timestamp: str | None = None
    sandbox_name: str | None = None
    sandbox_id: str | None = None
    seq: int | None = None
    data: Any = None

    @property
    def kind(self) -> EventKind:
        """The family of the event."""
        try:
            return EventKind(self.event_type)
        except ValueError:
            return EventKind.OTHER

    @property
    def is_sync(self) -> bool:
        """Whether this event marks the end of the initial replay."""
        return self.kind is EventKind.SYNC

    def is_about(self, name: str) -> bool:
        """Whether the event refers to the sandbox `name`."""
        return self.sandbox_name == name
