"""The `claude` kit forged without the CLI: its arguments, and an MCP server given by a mixin.

The same sandbox as `agent-kit-args`, from a package forged through the
socket alone, into a directory. The forge rebuilds the kit from its published
image: the daemon pulls and exports it, and the descriptor of the kit is read
from the image. The values of `Kit(args=…)` are checked as the CLI checks
them, against the values or the pattern the kit declares: a value the kit
refuses, or an argument it does not declare, is an `InvalidKitError` before
anything is created. They are then substituted in the commands of the kit and
set in its variables: the sandbox gets `CLAUDE_MODEL` and
`CLAUDE_REASONING_EFFORT`, and the install command of the kit writes them
into `~/.claude/settings.json`.

The MCP server of the examples is served by this script on a loopback port
of the host, the same at every run unless it is taken: the port is part of
the mixin, and so of the images the daemon keeps for it, which another port
would add to. `Mixin.mcp` registers it in Claude Code at install time
(`claude mcp add`, inside the sandbox): no file is written on the host and
nothing is registered with the daemon. Its bearer token, random and different
at every run, is given at creation in the variable the server names
(`McpServer.env`). The example reads what Claude Code registered, in
`~/.claude.json`, and runs the MCP client of the examples
(`common/programs/mcp_client.py`) inside the sandbox, at that URL and with
those headers: it opens a session as Claude Code would, lists the tools of
the server and calls `sum`, and the server checks the token of every request.
The mixin also registers a remote server, whose bearer is read from a
variable of the sandbox: the example only reads its registration, and never
calls it.

The kit is resolved as the CLI resolves it, the order of its effective
capabilities included: the daemon authorizes the credential it declares,
`anthropic`, as for a sandbox the CLI creates, and the proxy would write the
credential stored for it into the requests of the agent. The example checks
that the creation withholds nothing (`Created.withheld`); it never starts
Claude Code, so that no credential is sent.

Run it with:

    just example agent-kit-forge
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import common
import fastsandbox
from common import mcp
from fastsandbox import Kit, KitForge, McpServer, Mixin

if TYPE_CHECKING:
    from fastsandbox import Sandbox

OUTPUT = Path(__file__).parent / "target" / "forged" / "agent-kit-forge"
"""Where the package is written."""

MODEL = "claude-haiku-5-5"
"""The model chosen for the sandbox."""

EFFORT = "low"
"""The effort chosen for the sandbox."""

SERVER = "example-tools"
"""The name Claude Code knows the MCP server of the examples under."""

REMOTE = "https://mcp.example.com/mcp"
"""The remote MCP server registered beside it, in a reserved domain: never called."""

REMOTE_TOKEN = "EXAMPLE_DOCS_TOKEN"
"""The variable of the sandbox holding the bearer of the remote server."""

SETTINGS = "/home/agent/.claude/settings.json"
"""The settings of Claude Code in the sandbox, written by the install command of the kit."""

CLAUDE_CONFIG = "/home/agent/.claude.json"
"""The configuration of Claude Code in the sandbox, where `claude mcp add` registers servers."""

PORT = 47813
"""The loopback port the MCP server listens on, the same at every run; a free one when taken."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    print(f"the agents fastsandbox knows: {', '.join(fastsandbox.AGENTS)}")
    token = mcp.dummy_token()
    # The proxy of the sandbox forwards the requests to `host.docker.internal`
    # to the loopback of the host, as `localhost:<port>`.
    async with mcp.HttpServer(token, port=PORT) as http:
        tools = McpServer.host(SERVER, http.port)
        print(f"MCP server listening on {http.url}, given to Claude Code at {tools.url}")
        if http.port != PORT:
            print(f"the port {PORT} is taken: the mixin of this port is a new one for the daemon")
        # A remote server, called by the agent itself. A dummy bearer here;
        # for a real key, the placeholder of a `CustomSecret` for its host,
        # so that the sandbox never holds the key.
        docs = McpServer.remote("example-docs", REMOTE).with_bearer_env(REMOTE_TOKEN)
        kit = Kit(
            base="claude",
            mixins=(Mixin.mcp("claude", tools, docs),),
            args={"model": MODEL, "reasoningEffort": EFFORT},
        )
        print(
            f"forging the {kit.label} kit: rebuilt from its image, "
            f"with model={MODEL} and reasoningEffort={EFFORT}",
        )
        package = await KitForge(client).forge(kit, output=OUTPUT)
        artifact = package.kit_artifacts[0]
        print(
            f"the kit declares the arguments {', '.join(artifact['args'])}; "
            f"their values: {json.dumps(artifact['v3ArgValues'])}"
        )
        docs_token = mcp.dummy_token()
        env = {**tools.env(token), REMOTE_TOKEN: docs_token}
        name = fastsandbox.unique_name("example-kit-forge")
        creation = client.create(name, kit=package, env=env)
        async with creation as sandbox, sandbox.running():
            withheld = creation.created.withheld if creation.created is not None else []
            common.expect(not withheld, f"the daemon withholds {', '.join(withheld)}")
            print("the daemon withholds no credential: the anthropic one of the kit is authorized")
            await check_arguments(sandbox)
            registered = await registrations(sandbox)
            await check_server(sandbox, http, registered)
            check_remote(registered, docs.name, docs_token)


async def check_arguments(sandbox: Sandbox) -> None:
    """Checks that the sandbox got the arguments of the kit, in its variables and its settings."""
    output = await sandbox.exec(["printenv", "CLAUDE_MODEL", "CLAUDE_REASONING_EFFORT"], check=True)
    env = output.stdout.splitlines()
    if env != [MODEL, EFFORT]:
        raise common.ExampleError(f"unexpected environment: {env}")
    print(f"environment of the sandbox: CLAUDE_MODEL={MODEL}, CLAUDE_REASONING_EFFORT={EFFORT}")
    # Only the two fields the install command writes from the arguments are read.
    settings = json.loads(await sandbox.read_file(SETTINGS))
    if settings.get("model") != MODEL or settings.get("effortLevel") != EFFORT:
        raise common.ExampleError(
            f"unexpected settings: model {settings.get('model')!r}, "
            f"effortLevel {settings.get('effortLevel')!r}"
        )
    print(f"~/.claude/settings.json: model {MODEL}, effortLevel {EFFORT}")


async def registrations(sandbox: Sandbox) -> dict[str, Any]:
    """The MCP servers Claude Code registered in the sandbox, by name, read from its configuration.

    Raises:
        ExampleError: When the configuration registers no server.
    """
    servers = json.loads(await sandbox.read_file(CLAUDE_CONFIG)).get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        raise common.ExampleError(f"{CLAUDE_CONFIG} registers no MCP server")
    return servers


async def check_server(sandbox: Sandbox, http: mcp.HttpServer, registered: dict[str, Any]) -> None:
    """Uses the MCP server of the mixin from inside the sandbox, as Claude Code would.

    The MCP client of the examples opens a session at the URL and with the
    headers Claude Code registered, lists the tools and calls `sum`; the server
    is to receive the token given at creation in every request. Claude Code
    itself is not started.
    """
    server = registered.get(SERVER)
    if not isinstance(server, dict) or not isinstance(server.get("url"), str):
        raise common.ExampleError(f"{CLAUDE_CONFIG} registers no URL for {SERVER}")
    url: str = server["url"]
    headers = {str(key): str(value) for key, value in (server.get("headers") or {}).items()}
    print(f"~/.claude.json registers {SERVER}: {server.get('type')} {url}")
    client = await mcp.SandboxClient.install(sandbox)
    session = await client.session(url, [("sum", {"a": 2, "b": 3})], headers=headers)
    common.expect("sum" in session.tools, f"the server lists {session.tools}, no sum")
    answer = session.calls[0].text_or_raise() if session.calls else None
    common.expect(answer == "5", f"the server answered sum(2, 3) = {answer}")
    print(
        f"from inside the sandbox, the server lists {', '.join(session.tools)} "
        "and answers sum(2, 3) = 5"
    )
    if http.authorized == 0 or http.refused:
        raise common.ExampleError(
            f"the server received {http.authorized} requests with its token, {http.refused} without"
        )
    print(f"the server received the token given at creation ({http.authorized} requests)")


def check_remote(registered: dict[str, Any], name: str, token: str) -> None:
    """Checks the registration of the remote server `name`: its URL, and `token` as its bearer.

    The example never calls it.
    """
    server = registered.get(name)
    if not isinstance(server, dict):
        raise common.ExampleError(f"{CLAUDE_CONFIG} registers no {name}")
    bearer = (server.get("headers") or {}).get("Authorization") == f"Bearer {token}"
    common.expect(
        server.get("type") == "http" and server.get("url") == REMOTE and bearer,
        f"unexpected registration of {name}: {server.get('type')} {server.get('url')}, "
        f"bearer {'given' if bearer else 'not the one given'}",
    )
    print(f"~/.claude.json registers {name} at {REMOTE}, bearer from {REMOTE_TOKEN}")


if __name__ == "__main__":
    common.main(main)
