"""A sandbox, by name.

Life cycle, sessions, commands, files, ports, network rules, credentials,
kits, MCP servers and SSH.

A `Sandbox` is a handle by name: creating one checks nothing, every method
talks to the daemon. A sandbox only stays running while a session is open, so
code that works in one holds it with `async with sandbox.running():`.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from typing import TYPE_CHECKING, Any, Self

from pydantic import TypeAdapter

from .exceptions import SandboxTimeoutError
from .models import (
    AgentSessionSpec,
    AttachSpec,
    CredentialsOutcome,
    CredentialsUpdate,
    ExecInspect,
    ExecOutput,
    ExecSpec,
    LoadedServer,
    McpGateway,
    NetworkRule,
    PortBinding,
    RuleChangeResult,
    SandboxInfo,
    SavedImage,
    SwapOutcome,
    SwapRequest,
    TerminalSize,
    wire,
)
from .sessions import Interactive, Session
from .ssh import SshTunnel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping, Sequence

    from . import _native
    from .client import Client
    from .types import Command

__all__ = ["Sandbox"]

_PORTS = TypeAdapter(list[PortBinding])


_RULES = TypeAdapter(list[NetworkRule])


def _argv(command: Command) -> list[str]:
    """The argument list of a command."""
    if isinstance(command, str):
        return ["sh", "-c", command]
    return list(command)


class Sandbox:
    """A sandbox of the daemon, by name."""

    def __init__(self, native: _native.Sandbox, client: Client) -> None:
        self._native = native
        self._client = client

    @property
    def name(self) -> str:
        """The name of the sandbox."""
        return self._native.name

    @property
    def client(self) -> Client:
        """The client the sandbox is reached through."""
        return self._client

    @property
    def native(self) -> _native.Sandbox:
        """The handle of the native extension."""
        return self._native

    def __repr__(self) -> str:
        return f"Sandbox(name={self.name!r})"

    # Life cycle.

    async def inspect(self) -> SandboxInfo:
        """The current state of the sandbox."""
        return SandboxInfo.model_validate(await self._native.inspect())

    async def exists(self) -> bool:
        """Whether the sandbox exists."""
        return await self._native.exists()

    async def start(self, *, ssh_agent_socket: str | None = None) -> SandboxInfo:
        """Starts the sandbox (idempotent).

        It stops again about 30 s after the last session closes: hold one with
        `running()` or `hold_session()` while working in it.
        """
        return SandboxInfo.model_validate(await self._native.start(ssh_agent_socket))

    async def stop(self) -> SandboxInfo:
        """Stops the sandbox."""
        return SandboxInfo.model_validate(await self._native.stop())

    async def delete(self, *, force: bool = False, expected_id: str | None = None) -> None:
        """Deletes the sandbox.

        Args:
            force: Stops it first when it runs.
            expected_id: Refuses to delete a different sandbox that took the
                same name.
        """
        await self._native.delete(force, expected_id)

    async def force_delete(self) -> None:
        """Stops the sandbox if needed, then deletes it."""
        await self._native.delete(True, None)

    async def save(self, tag: str) -> SavedImage:
        """Saves the sandbox as the image `tag`, a template for new sandboxes."""
        return SavedImage.model_validate(await self._native.save(tag))

    async def set_working_dir(self, dir: str) -> None:
        """Sets the working directory of new sessions."""
        await self._native.set_working_dir(dir)

    async def allow_host_path(self, host_path: str | os.PathLike[str]) -> None:
        """Grants the sandbox access to an existing path of the host."""
        await self._native.allow_host_path(os.fspath(host_path))

    async def revoke_host_path(self, host_path: str | os.PathLike[str]) -> None:
        """Revokes access to a path of the host."""
        await self._native.revoke_host_path(os.fspath(host_path))

    async def vm_metrics(self) -> str:
        """The metrics of the virtual machine, in Prometheus text format."""
        return await self._native.vm_metrics()

    async def wait_running(self, timeout: float = 60.0, interval: float = 0.5) -> SandboxInfo:
        """Waits until the sandbox runs, polling every `interval` seconds.

        Raises:
            SandboxTimeoutError: When it does not run within `timeout` seconds.
        """
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            info = await self.inspect()
            if info.is_running:
                return info
            if asyncio.get_running_loop().time() >= deadline:
                raise SandboxTimeoutError(
                    f"sandbox {self.name} not running after {timeout}s",
                    operation="sandbox wait",
                    after=timeout,
                )
            await asyncio.sleep(interval)

    # Sessions.

    async def hold_session(self) -> Session:
        """Opens a session that keeps the sandbox running while it is held."""
        return Session(await self._native.hold_session())

    async def ensure_running(self) -> Session:
        """Starts the sandbox if needed and holds a session on it."""
        return Session(await self._native.ensure_running())

    @contextlib.asynccontextmanager
    async def running(self) -> AsyncIterator[Self]:
        """Keeps the sandbox running for the duration of the block.

        Example:
            >>> async with sandbox.running():
            ...     await sandbox.exec("make test")
        """
        session = await self.ensure_running()
        try:
            yield self
        finally:
            session.release()

    # Commands.

    async def exec(
        self,
        command: Command | ExecSpec,
        *,
        user: str | None = None,
        working_dir: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        check: bool = False,
    ) -> ExecOutput:
        """Runs a command to completion.

        Args:
            command: A shell script (run with `sh -c`), an argument list, or a
                full `ExecSpec`.
            user: User name or UID (`"0"` for root).
            working_dir: Working directory.
            env: Additional environment variables.
            timeout: Deadline of the execution, in seconds.
            check: Raises `CommandFailedError` on a non-zero exit code.
        """
        if isinstance(command, ExecSpec):
            spec = command
        else:
            spec = ExecSpec(
                cmd=_argv(command), user=user, working_dir=working_dir, env=dict(env or {})
            )
        output = ExecOutput.model_validate(await self._native.exec(wire(spec), timeout))
        return output.check() if check else output

    async def exec_inspect(self, exec_id: str) -> ExecInspect:
        """The state of the execution `exec_id`, while the daemon remembers it."""
        return ExecInspect.model_validate(await self._native.exec_inspect(exec_id))

    async def attach(
        self,
        command: Command | AttachSpec,
        *,
        tty: bool = False,
        size: tuple[int, int] | None = None,
        user: str | None = None,
        working_dir: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> Interactive:
        """Starts an interactive command.

        Args:
            command: A shell script, an argument list, or a full `AttachSpec`.
            tty: Allocates a pseudo-terminal.
            size: Initial `(width, height)` of the terminal.
            user: User name or UID.
            working_dir: Working directory.
            env: Additional environment variables.
        """
        if isinstance(command, AttachSpec):
            spec = command
        else:
            spec = AttachSpec(
                cmd=_argv(command),
                tty=tty,
                terminal_size=TerminalSize(width=size[0], height=size[1]) if size else None,
                user=user,
                working_dir=working_dir,
                env=dict(env or {}),
            )
        return Interactive(await self._native.attach(wire(spec)))

    async def agent_session(
        self,
        args: Sequence[str] | AgentSessionSpec = (),
        *,
        tty: bool = False,
        size: tuple[int, int] | None = None,
        working_dir: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> Interactive:
        """Starts the agent of the sandbox kit in an interactive session.

        Args:
            args: Arguments of the agent, as `sbx run AGENT -- ARGS` passes
                them, or a full `AgentSessionSpec`.
            tty: Allocates a pseudo-terminal; interactive agents expect one,
                non-interactive runs separate stdout and stderr without it.
            size: Initial `(width, height)` of the terminal.
            working_dir: Working directory.
            env: Additional environment variables.
        """
        if isinstance(args, AgentSessionSpec):
            spec = args
        else:
            spec = AgentSessionSpec(
                args=list(args),
                tty=tty,
                terminal_size=TerminalSize(width=size[0], height=size[1]) if size else None,
                working_dir=working_dir,
                env=dict(env or {}),
            )
        return Interactive(await self._native.agent_session(wire(spec)))

    # Files.

    async def upload_archive(self, dir: str, archive: bytes) -> None:
        """Extracts a tar archive into `dir` of the sandbox."""
        await self._native.upload_archive(dir, archive)

    async def download_archive(self, path: str) -> bytes:
        """A tar archive of `path` of the sandbox."""
        return await self._native.download_archive(path)

    async def write_file(
        self, path: str, contents: bytes | str, *, mode: int | None = None
    ) -> None:
        """Writes `contents` (UTF-8 for a string) to the file `path`."""
        data = contents.encode() if isinstance(contents, str) else contents
        await self._native.write_file(path, data, mode)

    async def read_file(self, path: str) -> bytes:
        """The contents of the file `path`."""
        return await self._native.read_file(path)

    async def read_text(self, path: str, encoding: str = "utf-8") -> str:
        """The contents of the file `path`, decoded."""
        return (await self.read_file(path)).decode(encoding)

    async def upload_dir(self, host_dir: str | os.PathLike[str], dir: str) -> None:
        """Copies the directory `host_dir` of the host, under its own name, into `dir`.

        `upload_dir("./project", "/work")` gives `/work/project/…`; to copy the
        contents alone, send a tar archive with `upload_archive`.
        """
        await self._native.upload_dir(os.fspath(host_dir), dir)

    async def download_dir(self, path: str, host_dir: str | os.PathLike[str]) -> None:
        """Copies `path` of the sandbox into the directory `host_dir` of the host."""
        await self._native.download_dir(path, os.fspath(host_dir))

    # Ports.

    async def ports(self) -> list[PortBinding]:
        """The published ports."""
        return _PORTS.validate_python(await self._native.ports())

    async def publish(self, *ports: PortBinding) -> list[PortBinding]:
        """Publishes ports; the result has the bindings the daemon applied."""
        return _PORTS.validate_python(await self._native.publish([wire(p) for p in ports]))

    async def unpublish(self, *ports: PortBinding) -> None:
        """Unpublishes ports."""
        await self._native.unpublish([wire(p) for p in ports])

    async def replace_desired_port(self, old: PortBinding, new: PortBinding) -> None:
        """Replaces a port the sandbox publishes when it starts."""
        await self._native.replace_desired_port(wire(old), wire(new))

    # Network.

    async def network_rules(self) -> list[NetworkRule]:
        """The network rules that apply to this sandbox."""
        return _RULES.validate_python(await self._native.network_rules())

    async def allow_hosts(self, *hosts: str) -> RuleChangeResult:
        """Allows hosts for this sandbox only."""
        return RuleChangeResult.model_validate(await self._native.allow_hosts(list(hosts)))

    async def deny_hosts(self, *hosts: str) -> RuleChangeResult:
        """Denies hosts for this sandbox only."""
        return RuleChangeResult.model_validate(await self._native.deny_hosts(list(hosts)))

    async def remove_hosts(self, *hosts: str) -> RuleChangeResult:
        """Removes the rules of this sandbox on hosts."""
        return RuleChangeResult.model_validate(await self._native.remove_hosts(list(hosts)))

    async def remove_network_rule(self, id: str) -> RuleChangeResult:
        """Removes the rule `id` of this sandbox."""
        return RuleChangeResult.model_validate(await self._native.remove_network_rule(id))

    # Credentials.

    async def push_credentials(self, update: CredentialsUpdate) -> CredentialsOutcome:
        """Pushes a credentials update: custom secrets, service credentials and their sources.

        Returns:
            The outcome; its `withheld` names the services the daemon gives nothing.
        """
        return CredentialsOutcome.model_validate(await self._native.push_credentials(wire(update)))

    async def push_service_secret(self, service: str, value: str) -> CredentialsOutcome:
        """Sets the secret of `service` for this sandbox.

        The proxy adds it to requests; the sandbox never sees it.

        Returns:
            The outcome; `service` is in its `withheld` when no kit of the sandbox is
            authorized its credential, and the proxy then injects nothing.
        """
        return CredentialsOutcome.model_validate(
            await self._native.push_service_secret(service, value)
        )

    async def remove_service_secret(self, service: str) -> CredentialsOutcome:
        """Removes the secret of `service` for this sandbox.

        Returns:
            The outcome of the update.
        """
        return CredentialsOutcome.model_validate(await self._native.remove_service_secret(service))

    # Kits.

    async def add_kit_artifact(self, artifact: Any) -> None:
        """Installs a kit artifact in place, in the running container."""
        await self._native.add_kit_artifact(artifact)

    async def swap_container(self, request: SwapRequest) -> SwapOutcome:
        """Replaces the container with one built with more kits."""
        return SwapOutcome.model_validate(await self._native.swap_container(wire(request)))

    # MCP.

    async def mcp_gateway(self) -> McpGateway:
        """The MCP gateway of the sandbox."""
        return McpGateway.model_validate(await self._native.mcp_gateway())

    async def load_mcp_server(self, server: str) -> LoadedServer:
        """Loads the registered MCP server `server` into the gateway."""
        return LoadedServer.model_validate(await self._native.load_mcp_server(server))

    async def unload_mcp_server(self, server: str) -> None:
        """Unloads the MCP server `server` from the gateway."""
        await self._native.unload_mcp_server(server)

    # SSH.

    async def ssh_tunnel(self) -> SshTunnel:
        """An SSH connection to the sandbox, as a byte tunnel."""
        return SshTunnel(await self._native.ssh_tunnel())
