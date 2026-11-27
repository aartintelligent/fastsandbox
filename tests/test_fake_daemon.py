"""The fake daemon of `fastsandbox.testing`."""

from __future__ import annotations

import asyncio

import fastsandbox
from fastsandbox.models import (
    PortBinding,
)
from fastsandbox.testing import FakeDaemon, PublishedKit, Request, Response, repository


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


def test_references_are_normalized_as_docker_does() -> None:
    assert repository("shell") == "docker.io/library/shell"
    assert repository("sbx/shell:latest") == "docker.io/sbx/shell"
    assert repository("docker.io/sbx/claude@sha256:abc") == "docker.io/sbx/claude"
    assert repository("localhost:5000/kits/tools:1") == "localhost:5000/kits/tools"


async def test_a_published_kit_of_ones_own_is_forged(
    client: fastsandbox.Client, daemon: FakeDaemon
) -> None:
    descriptor = {"schemaVersion": "3", "kind": "workload", "displayName": "Tools"}
    daemon.kits["registry.example.com/acme/tools"] = PublishedKit(descriptor, entrypoint=["tools"])
    # The forge only takes kits from the sources the daemon allows.
    daemon.settings["kit.allowedSources"] = ["docker.io/", "registry.example.com/"]
    package = await fastsandbox.KitForge(client).forge("registry.example.com/acme/tools:1")
    assert package.agent is not None
    assert package.agent.binary == "tools"


async def test_settings_the_fake_does_not_know_are_not_found(daemon: FakeDaemon) -> None:
    reader, writer = await asyncio.open_unix_connection(daemon.socket_path)
    writer.write(b"GET /daemon/settings/kit.unknown HTTP/1.1\r\nHost: d\r\n\r\n")
    await writer.drain()
    status = await reader.readline()
    writer.close()
    assert b" 404 " in status


async def test_images_the_fake_does_not_hold_are_not_exported(daemon: FakeDaemon) -> None:
    reader, writer = await asyncio.open_unix_connection(daemon.socket_path)
    writer.write(b"GET /docker/images/export?name=docker.io/sbx/none HTTP/1.1\r\nHost: d\r\n\r\n")
    await writer.drain()
    status = await reader.readline()
    writer.close()
    assert b" 404 " in status
