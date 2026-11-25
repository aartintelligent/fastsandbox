"""Plugging the local terminal into an interactive session.

The terminal is switched to raw mode, so that every key — Ctrl-C included —
reaches the program in the sandbox, and window size changes (`SIGWINCH`) are
forwarded. Standard input is read on a thread of its own: a blocking read must
not keep the program alive once the session has ended. When it ends — input
piped from a file — the relay types Ctrl-D, as a terminal would: closing the
input of a terminal session does not end the program.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import sys
import termios
import threading
import tty
from typing import TYPE_CHECKING

from fastsandbox import SandboxError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastsandbox import Interactive

__all__ = ["relay", "size"]

END_OF_INPUT = b"\x04"
"""End-of-transmission (Ctrl-D): what a terminal sends at the end of input."""

EXIT_TIMEOUT = 10.0
"""How long the exit code is awaited once the output has ended, in seconds."""

READ_SIZE = 1024
"""How many bytes of standard input are read at once."""


def size() -> tuple[int, int]:
    """The `(width, height)` of the local terminal, 80 x 24 when it is not a terminal."""
    try:
        columns, lines = os.get_terminal_size(sys.__stdout__.fileno() if sys.__stdout__ else 1)
    except OSError:
        return 80, 24
    return columns, lines


async def relay(session: Interactive) -> int:
    """Relays the local terminal to `session` until its output ends, and returns its exit code.

    Raises:
        SandboxError: When the connection breaks, or the exit code is not
            available in time.
    """
    with _raw_mode():
        keyboard = asyncio.create_task(_type_keys(session))
        resizer = asyncio.create_task(_follow_resizes(session))
        try:
            stdout = sys.stdout.buffer
            async for chunk in session:
                stdout.write(chunk.data)
                stdout.flush()
        finally:
            keyboard.cancel()
            resizer.cancel()
    return await session.wait(EXIT_TIMEOUT)


@contextlib.contextmanager
def _raw_mode() -> Iterator[None]:
    """Switches the terminal to raw mode for the block, when standard input is one."""
    fd = sys.stdin.fileno()
    if not os.isatty(fd):
        yield
        return
    saved = termios.tcgetattr(fd)
    tty.setraw(fd)
    try:
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


async def _type_keys(session: Interactive) -> None:
    """Sends what is typed to `session`, then Ctrl-D when standard input ends."""
    loop = asyncio.get_running_loop()
    keys: asyncio.Queue[bytes] = asyncio.Queue()

    def read() -> None:
        """Reads standard input on its own thread, until its end."""
        fd = sys.stdin.fileno()
        while True:
            try:
                data = os.read(fd, READ_SIZE)
            except OSError:
                data = b""
            try:
                loop.call_soon_threadsafe(keys.put_nowait, data)
            except RuntimeError:
                # The loop is closed: the example has ended.
                return
            if not data:
                return

    # A daemon thread: a pending read does not keep the program alive.
    threading.Thread(target=read, name="stdin", daemon=True).start()
    while data := await keys.get():
        await session.write(data)
    # The input stays open: the output ends when the program does.
    await session.write(END_OF_INPUT)


async def _follow_resizes(session: Interactive) -> None:
    """Resizes the terminal of `session` whenever the local window changes size."""
    loop = asyncio.get_running_loop()
    changed = asyncio.Event()
    loop.add_signal_handler(signal.SIGWINCH, changed.set)
    try:
        while True:
            await changed.wait()
            changed.clear()
            width, height = size()
            # A resize racing the end of the session is of no consequence.
            with contextlib.suppress(SandboxError):
                await session.resize(width, height)
    finally:
        loop.remove_signal_handler(signal.SIGWINCH)
