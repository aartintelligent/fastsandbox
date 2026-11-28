"""Helpers shared by the client and the framework: durations, names, awaitables, loops."""

from __future__ import annotations

import asyncio
import re
import secrets
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

__all__ = ["PerLoop", "as_coroutine", "parse_timeout", "unique_name"]


_DURATION = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|s|m|h|d)")


_UNITS = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_timeout(value: float | str | timedelta | None) -> float | None:
    """A timeout in seconds.

    From seconds, a `timedelta`, or a duration such as `"90s"`, `"10m"`, `"1h30m"`, `"500ms"`
    or `"1d"`.

    Raises:
        ValueError: When the duration cannot be read.

    """
    if value is None:
        return None
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, int | float):
        return float(value)
    text = value.strip().lower().replace(" ", "")
    parts = _DURATION.findall(text)
    if not parts or "".join(n + u for n, u in parts) != text:
        raise ValueError(f"invalid duration {value!r}: expected e.g. '90s', '10m' or '1h30m'")
    return sum(float(number) * _UNITS[unit] for number, unit in parts)


def unique_name(prefix: str = "fastsandbox") -> str:
    """A sandbox name unlikely to be taken: `prefix` and a random suffix."""
    return f"{prefix}-{secrets.token_hex(4)}"


async def as_coroutine[T](awaitable: Awaitable[T]) -> T:
    """`awaitable` as a coroutine, which `run_coroutine_threadsafe` requires."""
    return await awaitable


class PerLoop[T]:
    """A value made once per event loop, such as an asyncio lock or semaphore.

    An asyncio lock or semaphore belongs to the loop it first waits in, and raises
    `RuntimeError` when it waits in another: one held across the loops of `asyncio.run`, by an
    application or a kit cache, is made again in each. What it bounds, it bounds within one
    loop.
    """

    def __init__(self, make: Callable[[], T]) -> None:
        """Values made by `make`, the first time one is asked for in a loop."""
        self._make = make
        self._held: tuple[asyncio.AbstractEventLoop, T] | None = None

    def get(self) -> T:
        """The value of the running event loop, made now if it has none.

        Raises:
            RuntimeError: When no event loop runs.
        """
        loop = asyncio.get_running_loop()
        if self._held is None or self._held[0] is not loop:
            self._held = (loop, self._make())
        return self._held[1]
