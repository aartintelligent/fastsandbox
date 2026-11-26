"""The fake daemon of `fastsandbox.testing`."""

from __future__ import annotations

import asyncio

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


async def test_a_client_hanging_up_mid_request_leaves_the_daemon_serving(
    daemon: FakeDaemon,
) -> None:
    reader, writer = await asyncio.open_unix_connection(daemon.socket_path)
    # A body shorter than its announced length, then the end of the stream.
    writer.write(b'POST /sandbox HTTP/1.1\r\ncontent-length: 64\r\n\r\n{"name"')
    writer.write_eof()
    # The daemon closes the connection without an answer.
    async with asyncio.timeout(5):
        assert await reader.read() == b""
    writer.close()
    await writer.wait_closed()
    client = await fastsandbox.connect(daemon.socket_path)
    assert client.health.status
    assert daemon.requests_to("POST", "/sandbox") == []
