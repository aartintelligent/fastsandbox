"""Sessions of a sandbox.

The session that keeps a sandbox running, and interactive commands.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Self

from .models import AttachOutput, ExecInspect, OutputChunk

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from types import TracebackType

    from . import _native

__all__ = ["Interactive", "Session"]


class Session:
    """A session that keeps a sandbox running while it is held.

    Use it as an async context manager, or call `release()`; the sandbox stops
    about 30 s after the last session closes.
    """

    def __init__(self, native: _native.SessionGuard) -> None:
        self._native = native

    @property
    def sandbox(self) -> str:
        """The name of the sandbox."""
        return self._native.sandbox

    @property
    def is_connected(self) -> bool:
        """Whether the session is still open."""
        return self._native.is_connected

    def release(self) -> None:
        """Closes the session."""
        self._native.release()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()

    def __repr__(self) -> str:
        return f"Session(sandbox={self.sandbox!r}, connected={self.is_connected})"


class Interactive:
    """An interactive command or agent session.

    Write its standard input with `write` and `close_stdin`, read its output
    with `async for chunk in session`, resize its terminal, wait for its exit
    code; or `collect` everything at once. As an async context manager, it
    closes the standard input on exit.
    """

    def __init__(self, native: _native.ExecSession) -> None:
        self._native = native

    @property
    def id(self) -> str:
        """The id of the execution."""
        return self._native.id

    async def write(self, data: bytes | str) -> None:
        """Writes `data` (UTF-8 for a string) to the standard input."""
        await self._native.write(data.encode() if isinstance(data, str) else data)

    async def close_stdin(self) -> None:
        """Closes the standard input: the command reads end of file."""
        await self._native.close_stdin()

    def __aiter__(self) -> AsyncIterator[OutputChunk]:
        return self._chunks()

    async def _chunks(self) -> AsyncIterator[OutputChunk]:
        async for item in self._native:
            yield OutputChunk.model_validate(item)

    async def resize(self, width: int, height: int) -> None:
        """Resizes the terminal of a TTY session."""
        await self._native.resize(width, height)

    async def inspect(self) -> ExecInspect:
        """The state of the execution."""
        return ExecInspect.model_validate(await self._native.inspect())

    async def wait(self, timeout: float = 60.0) -> int:
        """Waits for the exit code, for at most `timeout` seconds."""
        return await self._native.wait(timeout)

    async def collect(self, stdin: bytes | str = b"", exit_timeout: float = 10.0) -> AttachOutput:
        """Writes `stdin`, closes it, and reads everything until the exit.

        Only possible before the session is used piece by piece.
        """
        data = stdin.encode() if isinstance(stdin, str) else stdin
        return AttachOutput.model_validate(await self._native.collect(data, exit_timeout))

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        with contextlib.suppress(Exception):
            await self.close_stdin()

    def __repr__(self) -> str:
        return f"Interactive(id={self.id!r})"
