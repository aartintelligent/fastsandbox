"""Type aliases shared by the client and the framework."""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .applications import FastSandbox

__all__ = ["Command", "Lifespan", "ProgressHandler", "VersionPolicy"]

Command = str | Sequence[str]
"""A command: a string runs through `sh -c`, a sequence is the argument list."""


VersionPolicy = Literal["strict", "warn", "ignore"]
"""What to do when the daemon reports an API version this release was not
audited on: refuse (`strict`), log a warning, or ignore it."""


Lifespan = Callable[
    ["FastSandbox"], contextlib.AbstractAsyncContextManager[Mapping[str, Any] | None]
]
"""An async context manager factory run around the life of the application;
what it yields becomes `Context.state`."""


ProgressHandler = Callable[[float, float | None, str | None], Awaitable[None] | None]
"""Receives `(progress, total, message)` from `Context.report_progress`."""
