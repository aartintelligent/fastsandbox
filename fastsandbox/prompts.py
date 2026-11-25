"""The approval prompts of the daemon."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import PromptEvent
from .streams import Stream

if TYPE_CHECKING:
    from . import _native

__all__ = ["Prompts"]


class Prompts:
    """The approval prompts of the daemon."""

    def __init__(self, native: _native.Prompts) -> None:
        self._native = native

    async def subscribe(self) -> Stream[PromptEvent]:
        """The pending prompts, then the new ones."""
        return Stream(await self._native.subscribe(), PromptEvent.model_validate)

    async def respond(self, id: str, option_id: str) -> None:
        """Answers the prompt `id` with the option `option_id`."""
        await self._native.respond(id, option_id)
