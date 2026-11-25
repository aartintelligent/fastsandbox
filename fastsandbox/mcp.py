"""The MCP gateway settings of the daemon."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import GatewayMode, McpServerCheck, RegistrationCheck, wire

if TYPE_CHECKING:
    from . import _native

__all__ = ["Mcp"]


class Mcp:
    """The MCP gateway settings of the daemon."""

    def __init__(self, native: _native.Mcp) -> None:
        self._native = native

    async def gateway_mode(self) -> GatewayMode:
        """How the gateway runs MCP servers."""
        return GatewayMode.model_validate(await self._native.gateway_mode())

    async def check_registration(self, server: McpServerCheck) -> RegistrationCheck:
        """Whether an MCP server definition can be registered."""
        return RegistrationCheck.model_validate(await self._native.check_registration(wire(server)))
