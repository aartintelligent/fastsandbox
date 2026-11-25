"""An MCP server loaded into the gateway of a sandbox, then called from inside, as its agent would.

The example registers its own script as a local MCP server (`sbx mcp add
--command`), loads it into the gateway of a shell sandbox through the socket,
and runs the MCP client of `common/programs/mcp_client.py` inside the
sandbox: through `http://mcp-gateway.docker.internal/mcp` it lists the tools
and calls `sum`. It then shows that the port of the gateway on the host
refuses a request that does not come through the proxy of the sandbox, and
what the client lists once the server is unloaded. The registration is
removed when the example ends.

What it measured on `sbx` v0.54.0, as the `mcp-gateway` example of
`docker-sandbox` did:

- The gateway answers inside the sandbox only: its port on the host answers
  `401 Unauthorized`, since the proxy of the sandbox adds the credential.
- Besides the tools of its servers, a gateway offers `mcp-find`, `mcp-add`,
  `mcp-config-set`, `mcp-exec` and `code-mode`. Tools are not prefixed by
  server.

Run it with:

    just example mcp-gateway
"""

from __future__ import annotations

import asyncio

import common
import fastsandbox
from common import kit, mcp

PING = b'{"jsonrpc":"2.0","id":1,"method":"ping"}'
"""An MCP request any server answers, sent to the gateway from the host."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    mode = await client.mcp.gateway_mode()
    print(f"MCP gateway of the daemon: {mode.decision}")
    package = await kit.package(client, "shell")
    name = fastsandbox.unique_name("example-mcp-gateway")

    # The registration is made before the sandbox and removed after it: the
    # `async with` blocks undo what they did in reverse order.
    async with (
        mcp.registered(client, f"{name}-tools") as registration,
        client.create(name, kit=package) as sandbox,
        sandbox.running(),
    ):
        server = registration.name
        mcp_client = await mcp.SandboxClient.install(sandbox)

        await sandbox.load_mcp_server(server)
        gateway = await sandbox.mcp_gateway()
        print(
            f"gateway {gateway.state or '?'}: servers {gateway.servers}, "
            f"static {gateway.static_servers}"
        )
        url = mcp.gateway_url(gateway)

        listing = await mcp_client.list_tools(url)
        print(f"{url} ({listing.server}) lists {listing.tools}")
        sum_tool = listing.tool("sum")
        if sum_tool is None:
            raise common.ExampleError("the gateway lists no sum tool")
        answer = await mcp_client.call(url, sum_tool, {"a": 2, "b": 3})
        print(f"{sum_tool}(2, 3) = {answer}")
        if answer != "5":
            raise common.ExampleError(f"the server answered {answer}, not 5")

        if gateway.port is not None:
            status = await status_line(gateway.port)
            print(f"from the host, port {gateway.port} of the gateway answers: {status}")

        await sandbox.unload_mcp_server(server)
        listing = await mcp_client.list_tools(url)
        print(f"once {server} is unloaded, the gateway lists {listing.tools}")


async def status_line(port: int) -> str:
    """The status line of the answer to an MCP request sent straight to `port` on the host.

    The request does not go through the proxy of a sandbox, which is what adds
    the credential of the gateway.
    """
    request = (
        f"POST /mcp HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Type: application/json\r\n"
        f"Accept: application/json, text/event-stream\r\nContent-Length: {len(PING)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode() + PING
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        writer.write(request)
        await writer.drain()
        answer = await reader.read()
    finally:
        writer.close()
        await writer.wait_closed()
    return answer.decode(errors="replace").partition("\r\n")[0]


if __name__ == "__main__":
    # `sbx` starts this same script as the MCP server of the examples.
    if not mcp.serve_if_requested():
        common.main(main)
