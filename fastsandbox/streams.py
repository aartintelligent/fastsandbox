"""Typed async iterators over the streams of the daemon."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from . import _native

__all__ = ["Stream"]


class Stream[T]:
    """A stream of the daemon: daemon events, prompts, creation or pull progress.

    Iterate it with `async for`; leave early with `aclose()` or by using it as
    an async context manager, which closes its connection to the daemon.
    """

    def __init__(self, native: _native.ItemStream, convert: Callable[[Any], T]) -> None:
        self._native = native
        self._convert = convert

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> T:
        return self._convert(await self._native.__anext__())

    async def aclose(self) -> None:
        """Stops the stream and closes its connection."""
        await self._native.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()
