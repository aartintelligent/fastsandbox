"""MCP gateways and servers."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from ._base import Model

__all__ = [
    "GatewayMode",
    "LoadedServer",
    "McpGateway",
    "McpServerCheck",
    "McpServerKind",
    "RegistrationCheck",
]


class McpServerKind(StrEnum):
    """Where an MCP server runs."""

    LOCAL = "local"
    REMOTE = "remote"


class McpGateway(Model):
    """MCP gateway of a sandbox.

    Attributes:
        state: Gateway state, e.g. `ready`.
        url: Gateway URL as seen from inside the sandbox.
        port: Port of the gateway on the host.
        static_servers: Whether the set of servers was fixed at creation.
        servers: Servers loaded into the gateway.
    """

    state: str | None = None
    url: str | None = None
    port: int | None = None
    static_servers: bool = Field(default=False, alias="static")
    servers: list[str] = []


class GatewayMode(Model):
    """Gateway mode of the daemon.

    Attributes:
        decision: Gateway in use, e.g. `local`.
        gateway_url: URL of a remote gateway, `none` for the local one.
        reason: Why this gateway is used.
    """

    decision: str
    gateway_url: str | None = None
    reason: str | None = None


class LoadedServer(Model):
    """A server loaded into the gateway of a sandbox.

    Attributes:
        sandbox: Sandbox name.
        server: Server name.
    """

    sandbox: str
    server: str


class McpServerCheck(Model):
    """An MCP server to check against the MCP policy.

    Attributes:
        name: Server name.
        kind: Where the server runs.
        command: Program and arguments of a local server.
        url: URL of a remote server.
    """

    name: str = Field(alias="Name")
    kind: McpServerKind = Field(alias="Type")
    command: list[str] = Field(default=[], alias="Command")
    url: str | None = Field(default=None, alias="URL")

    @classmethod
    def local(cls, name: str, command: list[str]) -> McpServerCheck:
        """A server started on the host by `command`."""
        return cls(name=name, kind=McpServerKind.LOCAL, command=command)

    @classmethod
    def remote(cls, name: str, url: str) -> McpServerCheck:
        """A server reached at `url`."""
        return cls(name=name, kind=McpServerKind.REMOTE, url=url)


class RegistrationCheck(Model):
    """Decision of the policy for an MCP server.

    Attributes:
        allowed: Whether the server may be registered.
        name: Server name.
    """

    allowed: bool
    name: str
