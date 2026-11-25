"""An MCP server added from inside a sandbox, through the tools of its gateway, as an agent can.

Besides the tools of its servers, the gateway of a sandbox offers tools of its
own: `mcp-find` searches the servers registered on the host, `mcp-add` loads
one into the gateway, `mcp-exec` calls a tool by name. The example registers a
remote MCP server on the host — the HTTP server of the examples, with a dummy
token stored as an `sbx` secret — without loading it into the gateway. The
MCP client inside the sandbox then finds it, adds it and calls its tools.

The addition outlives the session: the daemon lists the server among those of
the gateway, and the next session still offers its tools, until the program
unloads it through the socket. An agent can therefore load any server
registered on the host by itself; a sandbox created with a static MCP set
offers neither `mcp-find` nor `mcp-add` (see the `mcp-static` example). The
secret, its endpoint binding and the registration are removed when the
example ends.

What it measured on `sbx` v0.54.0, as the `mcp-dynamic` example of
`docker-sandbox` did:

- Tools are not prefixed by server: `mcp-add` refuses a server whose tool
  names are already taken.
- A server added from inside with `mcp-add` stays loaded: the socket lists it
  among the `servers` of the gateway, and later sessions offer it, until the
  program unloads it.

Run it with:

    just example mcp-dynamic
"""

from __future__ import annotations

import json

import common
import fastsandbox
from common import kit, mcp

PLACEHOLDER = "token"
"""The placeholder of the token in the header of the server."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    package = await kit.package(client, "shell")
    name = fastsandbox.unique_name("example-mcp-dynamic")
    server = f"{name}-remote"
    header = f"Authorization: Bearer ${{{PLACEHOLDER}}}"
    # A dummy credential, made for this run and removed with it.
    token = mcp.dummy_token()

    async with (
        mcp.HttpServer(token) as http,
        mcp.stored_secret(server, PLACEHOLDER, token),
        # Registered on the host, not loaded into the gateway: the sandbox
        # loads it itself.
        mcp.registered_remote(client, server, http.url, [header]),
        client.create(name, kit=package) as sandbox,
        sandbox.running(),
    ):
        mcp_client = await mcp.SandboxClient.install(sandbox)
        gateway = await sandbox.mcp_gateway()
        print(f"servers loaded by the daemon: {gateway.servers}")
        url = mcp.gateway_url(gateway)

        # One session: what `mcp-add` loads is offered to the same session.
        session = await mcp_client.session(
            url,
            [
                ("mcp-find", {"query": server}),
                ("mcp-add", {"name": server}),
                ("sum", {"a": 2, "b": 3}),
                ("mcp-exec", {"name": "echo", "arguments": {"text": "added from inside"}}),
            ],
        )
        print(f"the session opens with {session.tools}")
        if len(session.calls) != 4:
            raise common.ExampleError(f"the client answered {len(session.calls)} calls out of 4")
        found, added, total, echoed = (call.text_or_raise() for call in session.calls)
        print(f"mcp-find {server}: {names(found)}")
        print(f"mcp-add {server}: {added.strip()}")
        print(f"sum(2, 3) = {total}")
        print(f"mcp-exec echo: {echoed}")
        print(f"the session then offers {session.tools_after}")
        if total != "5":
            raise common.ExampleError(f"the added server answered {total}, not 5")

        print(f"the gateway reached the server with the token {http.authorized} times")
        gateway = await sandbox.mcp_gateway()
        print(f"servers loaded by the daemon: {gateway.servers}")
        if server not in gateway.servers:
            raise common.ExampleError("the daemon does not list the server added from inside")
        following = await mcp_client.list_tools(url)
        print(f"a new session offers {following.tools}")

        await sandbox.unload_mcp_server(server)
        following = await mcp_client.list_tools(url)
        print(f"unloaded through the socket: a new session offers {following.tools}")
        if following.tool("sum") is not None:
            raise common.ExampleError("the server is still offered")


def names(found: str) -> str:
    """The names in the answer of `mcp-find`, a JSON list of `{name, type}`.

    The answer itself when it is not one.
    """
    try:
        servers = json.loads(found)
    except ValueError:
        return found.strip()
    if not isinstance(servers, list):
        return found.strip()
    return str([entry["name"] for entry in servers if isinstance(entry, dict) and "name" in entry])


if __name__ == "__main__":
    common.main(main)
