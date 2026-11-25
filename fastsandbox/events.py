"""The event stream of the daemon."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import DaemonEvent
from .streams import Stream

if TYPE_CHECKING:
    from . import _native

__all__ = ["Events"]


class Events:
    """The event stream of the daemon."""

    def __init__(self, native: _native.Events) -> None:
        self._native = native

    async def subscribe(self) -> Stream[DaemonEvent]:
        """Every event: the current state replayed, a `sync` event, then the live events."""
        return Stream(await self._native.subscribe(), DaemonEvent.model_validate)

    async def subscribe_live(self) -> Stream[DaemonEvent]:
        """The live events only."""
        return Stream(await self._native.subscribe_live(), DaemonEvent.model_validate)
