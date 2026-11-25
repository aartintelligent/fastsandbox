"""A remote MCP server reached from a sandbox with a credential it never sees, then rotated.

The example serves the MCP tools over streamable HTTP on a loopback port of
the host, to requests carrying a bearer token only, and:

1. stores a dummy token as the `sbx` secret `mcp:<server>:token` — before the
   registration, since `sbx mcp add` probes the server;
2. registers the server with `sbx mcp add --url … --header 'Authorization:
   Bearer ${token}'`, and loads it into the gateway of a shell sandbox;
3. calls `echo` with the MCP client inside the sandbox: the gateway fills the
   header from the secret store of the host, so the server sees the token
   while the sandbox never holds it, which the example checks;
4. rotates the token on the server, shows the gateway refused with the old
   secret, stores the new one, and shows what the gateway needs to use it.

The secret, its endpoint binding and the registration are removed when the
example ends.

What it measured on `sbx` v0.54.0, as the `mcp-remote` example of
`docker-sandbox` did:

- `sbx mcp add --url` probes the server: one that answers `401` without OAuth
  metadata is refused, so a header secret is stored before the registration.
  The first connection adds a `mcp:<server>:<placeholder>:endpoint` entry
  that binds the secret to the URL and outlives it; the example removes both.
- A gateway fills the header when it connects to the server and keeps that
  connection: a rotated secret is used once the server is unloaded and loaded
  again.

Run it with:

    just example mcp-remote
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import common
import fastsandbox
from common import kit, mcp

if TYPE_CHECKING:
    from fastsandbox import Sandbox

PLACEHOLDER = "token"
"""The placeholder of the token in the header of the server."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    package = await kit.package(client, "shell")
    name = fastsandbox.unique_name("example-mcp-remote")
    server = f"{name}-remote"
    header = f"Authorization: Bearer ${{{PLACEHOLDER}}}"
    # A dummy credential, made for this run and removed with it.
    token = mcp.dummy_token()

    async with mcp.HttpServer(token) as http:
        print(f"MCP server listening on {http.url}")
        # The secret is stored before the registration, which probes the
        # server, and removed after it; the sandbox goes first.
        async with (
            mcp.stored_secret(server, PLACEHOLDER, token),
            mcp.registered_remote(client, server, http.url, [header]),
            client.create(name, kit=package) as sandbox,
            sandbox.running(),
        ):
            mcp_client = await mcp.SandboxClient.install(sandbox)
            url = mcp.gateway_url(await sandbox.mcp_gateway())

            await sandbox.load_mcp_server(server)
            session = await mcp_client.list_tools(url)
            print(f"the gateway lists {session.tools}")
            print(f"echo answered: {await echo(mcp_client, url)}")
            print(f"the server accepted {http.authorized} requests carrying the token")
            if http.authorized == 0:
                raise common.ExampleError("no request carried the token")
            await ensure_absent(sandbox, token)

            rotated = mcp.dummy_token()
            http.rotate_token(rotated)
            refused = http.refused
            try:
                answer = await echo(mcp_client, url)
                print(f"token rotated on the server, echo still answers: {answer}")
            except common.ExampleError as error:
                print(f"token rotated on the server, the old secret fails: {error}")
            print(f"the server refused {http.refused - refused} requests")

            await mcp.set_secret(server, PLACEHOLDER, rotated)
            try:
                answer = await echo(mcp_client, url)
                print(f"new secret stored, echo answers: {answer}")
            except common.ExampleError as error:
                print(f"new secret stored, echo still fails: {error}")
                # The gateway keeps its connection to the server, and the
                # header it sent: a new connection takes the new secret.
                await sandbox.unload_mcp_server(server)
                await sandbox.load_mcp_server(server)
                print(f"server reloaded, echo answers: {await echo(mcp_client, url)}")
            await ensure_absent(sandbox, rotated)
            await sandbox.unload_mcp_server(server)


async def echo(client: mcp.SandboxClient, url: str) -> str:
    """Calls `echo` through the gateway at `url`, from inside the sandbox.

    Raises:
        ExampleError: When the client fails or the tool reports an error.
    """
    return await client.call(url, "echo", {"text": "hello from the sandbox"})


async def ensure_absent(sandbox: Sandbox, token: str) -> None:
    """Checks that `token` appears nowhere in the environment of the sandbox.

    Raises:
        ExampleError: When the sandbox can see the token.
    """
    env = await sandbox.exec(["env"], check=True)
    if token in env.stdout:
        raise common.ExampleError("the token is visible inside the sandbox")
    print("the token is nowhere in the environment of the sandbox")


if __name__ == "__main__":
    common.main(main)
