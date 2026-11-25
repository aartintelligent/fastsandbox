"""The fake daemon of `fastsandbox.testing`."""

from __future__ import annotations

import fastsandbox
from fastsandbox.models import (
    PortBinding,
)
from fastsandbox.testing import FakeDaemon, Request, Response


async def test_routes_can_be_replaced(
    client: fastsandbox.Client, daemon: FakeDaemon, package: fastsandbox.KitPackage
) -> None:
    from fastsandbox.testing import Response

    @daemon.route("GET", "/sandbox/{name}/ports")
    def ports(request: Request) -> Response:
        return Response(200, [{"sandbox_port": 80, "host_port": 8080, "protocol": "tcp"}])

    async with client.create(kit=package) as sandbox:
        assert await sandbox.ports() == [PortBinding.tcp(80, 8080)]
