"""The SSH tunnel of a sandbox."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from types import TracebackType

    from . import _native

__all__ = ["SshTunnel"]


class SshTunnel:
    """A byte tunnel to the SSH server of a sandbox.

    The server accepts any user, `root` included, without credentials: whoever
    holds the tunnel is `root` in the sandbox. Keep it to trusted code.
    """

    def __init__(self, native: _native.SshTunnel) -> None:
        self._native = native

    async def read(self, size: int = 65536) -> bytes:
        """Reads at most `size` bytes; `b""` is the end of the stream."""
        return await self._native.read(size)

    async def write(self, data: bytes) -> None:
        """Writes `data` to the tunnel."""
        await self._native.write(data)

    async def close(self) -> None:
        """Closes the tunnel."""
        await self._native.close()

    async def proxy_stdio(self) -> None:
        """Relays the tunnel to the standard input and output of the process.

        The job of an OpenSSH `ProxyCommand` (see `fastsandbox ssh-proxy`).
        """
        await self._native.proxy_stdio()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()
