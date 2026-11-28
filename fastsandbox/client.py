"""The client of the daemon: `connect()` and the handles it gives.

`await fastsandbox.connect()` opens a client: it reaches the `sandboxd` socket
of the current user, checks the health of the daemon and its API version.
Every other handle comes from it.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import _native
from .daemon import Daemon
from .events import Events
from .exceptions import NotFoundError
from .images import Images
from .kits import Kit, KitCache, KitPackage
from .mcp import Mcp
from .models import Created, CreateRequest, Health, PortBinding, PullPolicy, Workspace
from .policy import Policy
from .prompts import Prompts
from .sandbox import Sandbox
from .sandboxes import Sandboxes
from .utils import unique_name

if TYPE_CHECKING:
    from collections.abc import Coroutine, Generator, Mapping, Sequence
    from types import TracebackType

    from .types import VersionPolicy

__all__ = ["Client", "Creation", "connect"]


async def _left_nothing(creating: Coroutine[Any, Any, Created], sandbox: Sandbox) -> Created:
    """What `creating`, the creation of `sandbox`, answers; on a cancellation, nothing left.

    The request may have reached the daemon when the caller is cancelled, by a timeout or
    Ctrl-C: the creation then goes on to its end, and the sandbox it made is deleted. One that
    fails made none, and the sandbox of that name the daemon refused to replace is another's,
    left as it is. Cancelled again while it waits, it cancels the creation.
    """
    # `asyncio.wait` leaves the creation running when the caller is cancelled.
    task = asyncio.ensure_future(creating)
    try:
        await asyncio.wait([task])
    except asyncio.CancelledError:
        try:
            await asyncio.wait([task])
        except asyncio.CancelledError:
            task.cancel()
            raise
        if not task.cancelled() and task.exception() is None:
            with contextlib.suppress(NotFoundError):
                await sandbox.force_delete()
        raise
    return task.result()


async def connect(
    socket: str | os.PathLike[str] | None = None,
    *,
    timeout: float | None = None,
    long_operation_timeout: float | None = None,
    version_policy: VersionPolicy = "strict",
) -> Client:
    """Connects to the daemon.

    Args:
        socket: The socket path; `DOCKER_SANDBOXES_API`, then the state
            directory of `sbx`, by default.
        timeout: Deadline of ordinary requests, in seconds.
        long_operation_timeout: Deadline of long operations (creation, image
            pulls), in seconds.
        version_policy: What to do with an API version this release was not
            audited on.

    Raises:
        DaemonUnavailableError: When the daemon cannot be reached.
        UnsupportedVersionError: When its API version is not supported and
            `version_policy` is `strict`.
    """
    native = await _native.connect(
        os.fspath(socket) if socket is not None else None,
        timeout,
        long_operation_timeout,
        version_policy,
    )
    return Client(native)


class Client:
    """A connection to the daemon: the entry point of every other handle.

    It can be used as an async context manager; closing it releases nothing,
    connections are opened per request.
    """

    def __init__(self, native: _native.Client, *, kits: KitCache | None = None) -> None:
        self._native = native
        self._kits = kits

    @property
    def native(self) -> _native.Client:
        """The handle of the native extension."""
        return self._native

    @property
    def socket_path(self) -> Path:
        """The socket the client talks to."""
        return Path(self._native.socket_path)

    @property
    def health(self) -> Health:
        """The health the daemon reported when the client connected."""
        return Health.model_validate(self._native.health)

    @property
    def kits(self) -> KitCache:
        """The kit cache `create` takes packages from: the one of the process by default."""
        if self._kits is None:
            self._kits = KitCache.default()
        return self._kits

    @property
    def daemon(self) -> Daemon:
        """The daemon: health, settings, log levels, disk usage."""
        return Daemon(self._native.daemon())

    @property
    def sandboxes(self) -> Sandboxes:
        """The collection of sandboxes."""
        return Sandboxes(self._native.sandboxes(), self)

    @property
    def images(self) -> Images:
        """The images of the daemon."""
        return Images(self._native.images())

    @property
    def events(self) -> Events:
        """The event stream of the daemon."""
        return Events(self._native.events())

    @property
    def policy(self) -> Policy:
        """The network policy."""
        return Policy(self._native.policy())

    @property
    def mcp(self) -> Mcp:
        """The MCP gateway settings."""
        return Mcp(self._native.mcp())

    @property
    def prompts(self) -> Prompts:
        """The approval prompts of the daemon."""
        return Prompts(self._native.prompts())

    def sandbox(self, name: str) -> Sandbox:
        """The handle of the sandbox `name`; nothing is checked until it is used."""
        return Sandbox(self._native.sandbox(name), self)

    async def package(self, kit: Kit | KitPackage | str) -> KitPackage:
        """The package of `kit`.

        A kit is forged without the `sbx` CLI on first use, or compiled by it for a cache
        given the CLI (see `KitCache`); a package is returned as is.
        """
        if isinstance(kit, KitPackage):
            return kit
        return await self.kits.package(self, kit)

    def create(
        self,
        name: str | None = None,
        *,
        kit: Kit | KitPackage | str | None = "shell",
        request: CreateRequest | None = None,
        workspace: str | os.PathLike[str] | None = None,
        clone: bool = False,
        workspaces: Sequence[Workspace] = (),
        env: Mapping[str, str] | None = None,
        ports: Sequence[PortBinding] = (),
        cpus: int | None = None,
        memory: str | None = None,
        template: str | None = None,
        pull_policy: PullPolicy | None = None,
    ) -> Creation:
        """Creates a sandbox.

        Await the result to get the sandbox, which stays until deleted; or use
        it as an async context manager, which deletes the sandbox on exit.

        Example:
            >>> async with client.create(kit="shell") as sandbox:
            ...     async with sandbox.running():
            ...         await sandbox.exec("uname -a")

        Args:
            name: The sandbox name; a unique one by default.
            kit: The kit, compiled on first use; `None` to create from
                `request` alone, e.g. with a `template`.
            request: A full creation request; the other arguments adjust it.
            workspace: A host directory mounted as workspace, at its own path.
            clone: The agent works on a private clone of the Git repository of
                `workspace` instead of the directory itself.
            workspaces: Further directories or files to mount.
            env: Environment variables of the sandbox.
            ports: Ports published from the start.
            cpus: Number of virtual CPUs.
            memory: Memory limit in `sbx` notation, e.g. `4g`.
            template: Image to start from, e.g. one saved with `Sandbox.save`.
            pull_policy: When to pull kit images.
        """
        overrides: dict[str, Any] = {
            "workspace": os.fspath(workspace) if workspace is not None else None,
            "clone": clone or None,
            "cpus": cpus,
            "memory": memory,
            "template": template,
            "pull_policy": pull_policy,
        }
        return Creation(
            self,
            name or (request.name if request is not None else unique_name()),
            kit,
            request,
            {key: value for key, value in overrides.items() if value is not None},
            list(workspaces),
            dict(env or {}),
            list(ports),
        )

    async def __aenter__(self) -> Client:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def __repr__(self) -> str:
        return f"Client(socket_path={str(self.socket_path)!r})"


class Creation:
    """A sandbox being created.

    Await it, or use it as an async context manager that deletes the sandbox on exit. Cancelled
    while the daemon creates the sandbox, it waits for the creation to end and deletes the
    sandbox it made.
    """

    def __init__(
        self,
        client: Client,
        name: str,
        kit: Kit | KitPackage | str | None,
        request: CreateRequest | None,
        overrides: dict[str, Any],
        workspaces: list[Workspace],
        env: dict[str, str],
        ports: list[PortBinding],
    ) -> None:
        self._client = client
        self.name = name
        self._kit = kit
        self._request = request
        self._overrides = overrides
        self._workspaces = workspaces
        self._env = env
        self._ports = ports
        self._sandbox: Sandbox | None = None
        self.created: Created | None = None

    async def _create(self) -> Sandbox:
        """Creates the sandbox."""
        package = await self._client.package(self._kit) if self._kit is not None else None
        if self._request is not None:
            request = self._request.model_copy(update={"name": self.name})
        elif package is not None:
            request = package.request(self.name)
        else:
            raise ValueError("a kit or a request is needed to create a sandbox")
        request = request.model_copy(
            update={
                **self._overrides,
                "additional_workspaces": [*request.additional_workspaces, *self._workspaces],
                "environment": {**request.environment, **self._env},
                "ports": [*request.ports, *self._ports],
            }
        )
        if package is not None:
            creating = package.create_with(self._client, request)
        else:
            creating = self._client.sandboxes.create(request)
        self.created = await _left_nothing(creating, self._client.sandbox(self.name))
        self._sandbox = self._client.sandbox(self.name)
        return self._sandbox

    def __await__(self) -> Generator[Any, None, Sandbox]:
        return self._create().__await__()

    async def __aenter__(self) -> Sandbox:
        return await self._create()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._sandbox is not None:
            with contextlib.suppress(NotFoundError):
                await self._sandbox.force_delete()
