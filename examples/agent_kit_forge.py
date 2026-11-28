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
of the host. `Mixin.mcp` registers it in Claude Code at install time
(`claude mcp add`, inside the sandbox): no file is written on the host and
nothing is registered with the daemon. Its bearer token, random and different
at every run, is given at creation in the variable the server names
(`McpServer.env`). The example then sends, from inside the sandbox, the
`initialize` request Claude Code sends, to the URL and with the header it
registered, and checks that the server received the token. The mixin also
registers a remote server, whose bearer is read from a variable of the
sandbox: the example only reads its registration, and never calls it.

The kit is resolved as the CLI resolves it, the order of its effective
capabilities included: the daemon authorizes the credential it declares,
`anthropic`, as for a sandbox the CLI creates, and the proxy would write the
credential stored for it into the requests of the agent. The example never
starts Claude Code, so that none is sent.

Run it with:

    just example agent-kit-forge
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

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

REGISTERED = """
import json, os, sys
server = json.load(open("/home/agent/.claude.json"))["mcpServers"][sys.argv[1]]
bearer = server.get("headers", {}).get("Authorization") == "Bearer " + os.environ[sys.argv[2]]
print(server["type"], server["url"], bearer)
"""
"""Prints the type and URL Claude Code registered for the server named in its first argument,
and whether its bearer is the content of the variable named in the second."""

INITIALIZE = """
import json, sys, urllib.request
server = json.load(open("/home/agent/.claude.json"))["mcpServers"][sys.argv[1]]
body = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-03-26", "capabilities": {},
    "clientInfo": {"name": "agent-kit-forge", "version": "0.0.0"}}}
headers = dict(server.get("headers", {}))
headers["Content-Type"] = "application/json"
headers["Accept"] = "application/json, text/event-stream"
request = urllib.request.Request(server["url"], json.dumps(body).encode(), headers)
print(server["type"], server["url"], urllib.request.urlopen(request, timeout=30).status)
"""
"""Sends, from inside the sandbox, the `initialize` request of an MCP client to the URL and
with the headers Claude Code registered for the server named in its argument, and prints the
status of the answer."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    print(f"the agents fastsandbox knows: {', '.join(fastsandbox.AGENTS)}")
    token = mcp.dummy_token()
    # The proxy of the sandbox forwards the requests to `host.docker.internal`
    # to the loopback of the host, as `localhost:<port>`.
    async with mcp.HttpServer(token) as http:
        tools = McpServer.host(SERVER, http.port)
        print(f"MCP server listening on {http.url}, given to Claude Code at {tools.url}")
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
        env = {**tools.env(token), REMOTE_TOKEN: mcp.dummy_token()}
        name = fastsandbox.unique_name("example-kit-forge")
        async with client.create(name, kit=package, env=env) as sandbox, sandbox.running():
            await check_arguments(sandbox)
            await check_server(sandbox, http)
            registered = await sandbox.exec(
                ["python3", "-c", REGISTERED, docs.name, REMOTE_TOKEN], check=True
            )
            if registered.stdout.strip() != f"http {REMOTE} True":
                raise common.ExampleError(
                    f"unexpected registration of {docs.name}: {registered.stdout.strip()}"
                )
            print(f"~/.claude.json registers {docs.name} at {REMOTE}, bearer from {REMOTE_TOKEN}")


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


async def check_server(sandbox: Sandbox, http: mcp.HttpServer) -> None:
    """Checks that Claude Code got the MCP server of the mixin, without starting Claude Code.

    The server is to be reached from the sandbox with the token given at creation.
    """
    answered = await sandbox.exec(["python3", "-c", INITIALIZE, SERVER], check=True)
    print(f"~/.claude.json registers {SERVER}, which answers: {answered.stdout.strip()}")
    if not answered.stdout.strip().endswith(" 200"):
        raise common.ExampleError("the server did not answer the registered request")
    if http.authorized == 0 or http.refused:
        raise common.ExampleError(
            f"the server received {http.authorized} requests with its token, {http.refused} without"
        )
    print(f"the server received the token given at creation ({http.authorized} request)")


if __name__ == "__main__":
    common.main(main)
