"""Kits forged without the `sbx` CLI, against the real daemon."""

from __future__ import annotations

import asyncio
import json
import secrets
from pathlib import Path

import fastsandbox
from fastsandbox import Kit, KitDescriptor, KitForge, LifecycleStep, McpServer, Mixin

MIXIN = {
    "schemaVersion": "3",
    "kind": "mixin",
    "displayName": "Live tools",
    "capabilities": [
        {
            "type": "com.docker.sandbox/lifecycle@1",
            "config": {
                "install": [{"command": "echo installed > /tmp/live-tools", "user": "agent"}]
            },
        }
    ],
}

PORT = 47814
"""The port of the server of the host: part of the mixin, and so of the images the daemon keeps
for it, the same at every run unless it is taken."""

INITIALIZE = """
import json, sys, urllib.request
server = json.load(open("/home/agent/.claude.json"))["mcpServers"][sys.argv[1]]
body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}).encode()
headers = {**server.get("headers", {}), "Content-Type": "application/json"}
request = urllib.request.Request(server["url"], body, headers)
print(server["type"], server["url"], urllib.request.urlopen(request, timeout=30).status)
"""
"""Sends a request to the URL and with the headers Claude Code registered for the server named
in its argument, from inside the sandbox, and prints the status of the answer."""


async def test_a_forged_kit_and_its_mixin_create_a_sandbox(
    client: fastsandbox.Client, tmp_path: Path
) -> None:
    tools = tmp_path / "live-tools"
    tools.mkdir()
    (tools / "spec.yaml").write_text(json.dumps(MIXIN))
    package = await KitForge(client).forge(Kit(base="shell", mixins=(str(tools),)))
    assert package.dir is None
    assert package.compiled_api == client.health.api_version
    async with (
        client.create(fastsandbox.unique_name("live-forge"), kit=package) as sandbox,
        sandbox.running(),
    ):
        assert await sandbox.read_text("/tmp/live-tools") == "installed\n"


async def test_a_mixin_written_in_python_runs_its_install_commands(
    client: fastsandbox.Client,
) -> None:
    step = LifecycleStep(command='echo "written as $(id -un)" > /tmp/live-written')
    descriptor = (
        KitDescriptor.mixin("Live written")
        .with_install(step.as_user("agent"))
        .with_network_allow("example-live-mixin.invalid:443")
    )
    written = Mixin(reference="/kits/live-written", descriptor=descriptor)
    package = await KitForge(client).forge(Kit(base="shell", mixins=(written,)))
    assert package.kit_refs[1:] == ["/kits/live-written"]
    async with (
        client.create(fastsandbox.unique_name("live-written"), kit=package) as sandbox,
        sandbox.running(),
    ):
        assert await sandbox.read_text("/tmp/live-written") == "written as agent\n"


async def test_an_agent_kit_is_forged_with_its_agent(client: fastsandbox.Client) -> None:
    package = await client.package("claude")
    assert package.agent is not None
    assert package.agent.name == "claude"
    assert "api.anthropic.com" in package.agent.hosts()


async def test_claude_reaches_a_server_of_the_host_given_by_a_mixin(
    client: fastsandbox.Client,
) -> None:
    received: list[dict[str, str]] = []

    async def answer(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # A stand-in for the MCP server: it records the headers of the request.
        head = (await reader.readuntil(b"\r\n\r\n")).decode()
        lines = head.split("\r\n")[1:]
        headers = {k.lower(): v for k, _, v in (line.partition(": ") for line in lines if line)}
        await reader.readexactly(int(headers.get("content-length", "0")))
        received.append(headers)
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}")
        await writer.drain()
        writer.close()

    try:
        server = await asyncio.start_server(answer, "127.0.0.1", PORT)
    except OSError:
        server = await asyncio.start_server(answer, "127.0.0.1", 0)
    async with server:
        port = server.sockets[0].getsockname()[1]
        tools = McpServer.host("live-tools", port)
        token = f"live-{secrets.token_hex(8)}"
        kit = Kit(base="claude", mixins=(Mixin.mcp("claude", tools),))
        package = await KitForge(client).forge(kit)
        async with (
            client.create(
                fastsandbox.unique_name("live-mcp"), kit=package, env=tools.env(token)
            ) as sandbox,
            sandbox.running(),
        ):
            # Claude Code is never started: the request is the one it would send.
            answered = await sandbox.exec(["python3", "-c", INITIALIZE, tools.name], check=True)
    assert answered.stdout.strip() == f"http {tools.url} 200"
    # The proxy forwards the request to the loopback of the host under its loopback name,
    # which a server guarded against DNS rebinding accepts, with the token given at creation.
    assert [(h["host"], h["authorization"]) for h in received] == [
        (f"localhost:{port}", f"Bearer {token}")
    ]
