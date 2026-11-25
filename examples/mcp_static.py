"""A sandbox created with a fixed set of MCP servers, as `sbx create --static-mcp` does.

The example registers its own script as a local MCP server, then creates a
shell sandbox whose creation request names it as the static MCP set
(`CreateRequest.with_static_mcp_servers`): the gateway serves it from the
start, without a load. The MCP client inside the sandbox lists the tools and
calls `host_time`.

A static gateway offers neither `mcp-find` nor `mcp-add`: the sandbox cannot
load other servers by itself, which a dynamic gateway lets it do (see the
`mcp-dynamic` example). The program keeps that power: the daemon still
unloads and loads servers of a static set through the socket, and the example
shows the listing after each. The registration is removed when the example
ends.

What it measured on `sbx` v0.54.0, as the `mcp-static` example of
`docker-sandbox` did: a static gateway offers only `mcp-exec` and `code-mode`
besides the tools of its servers, so a runner that must fix the MCP servers
of a sandbox creates it with a static set.

Run it with:

    just example mcp-static
"""

from __future__ import annotations

import common
import fastsandbox
from common import kit, mcp


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    package = await kit.package(client, "shell")
    name = fastsandbox.unique_name("example-mcp-static")

    async with mcp.registered(client, f"{name}-tools") as registration:
        server = registration.name
        # The creation request of the kit, with the static MCP set: the
        # gateway of the sandbox serves these servers, and only these.
        request = package.request(name).with_static_mcp_servers(server)
        async with (
            client.create(name, kit=package, request=request) as sandbox,
            sandbox.running(),
        ):
            mcp_client = await mcp.SandboxClient.install(sandbox)
            gateway = await sandbox.mcp_gateway()
            print(
                f"gateway {gateway.state or '?'}: servers {gateway.servers}, "
                f"static {gateway.static_servers}"
            )
            url = mcp.gateway_url(gateway)

            listing = await mcp_client.list_tools(url)
            print(f"without any load, the gateway lists {listing.tools}")
            if listing.tool("mcp-add") is not None or listing.tool("mcp-find") is not None:
                raise common.ExampleError("a static gateway offers mcp-add or mcp-find")
            print("no mcp-find nor mcp-add: the sandbox cannot load servers by itself")
            host_time = listing.tool("host_time")
            if host_time is None:
                raise common.ExampleError("the gateway lists no host_time tool")
            answer = await mcp_client.call(url, host_time, {})
            print(f"{host_time}() = {answer}")

            # The program, unlike the sandbox, still changes the set.
            await sandbox.unload_mcp_server(server)
            listing = await mcp_client.list_tools(url)
            print(f"unloaded from the static set: {listing.tools}")
            await sandbox.load_mcp_server(server)
            listing = await mcp_client.list_tools(url)
            print(f"loaded again: {listing.tools}")


if __name__ == "__main__":
    # `sbx` starts this same script as the MCP server of the examples.
    if not mcp.serve_if_requested():
        common.main(main)
