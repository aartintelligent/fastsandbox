"""MCP for the examples: the tools, their registration with `sbx`, a gateway checked from inside.

MCP servers are registered on the host with `sbx mcp add`; the daemon then
loads them into the gateway of a sandbox. The gateway answers inside the
sandbox only: its port on the host refuses requests that do not come through
the proxy of the sandbox. A client therefore checks a gateway from inside:
`SandboxClient` copies the MCP client of `programs/mcp_client.py` into the
sandbox and runs it there.

The tools are served with the official MCP Python SDK (`mcp`, the `examples`
dependency group), in two ways:

- **Local server**: an example registers its own script, started with
  `SERVE_ARG`; started that way, it serves the tools on standard input and
  output instead of running the example (`serve_if_requested`).
- **Remote server**: `HttpServer` serves the same tools over streamable HTTP
  on a loopback port of the host, and only to requests carrying its bearer
  token, registered with a header whose `${token}` placeholder `sbx` fills
  from a secret it stores (`set_secret`).
- **Server given by a mixin**: the same `HttpServer`, which the agent reaches
  from the sandbox at `host.docker.internal` (`fastsandbox.McpServer.host`),
  registered in the agent by a mixin rather than with `sbx`. The proxy of the
  sandbox forwards its requests to the loopback of the host as
  `localhost:<port>`.

The registrations, the secrets and the `:endpoint` bindings `sbx` adds are
removed when an example ends: `registered`, `registered_remote` and
`stored_secret` are async context managers that undo what they did.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import secrets
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import uvicorn
from mcp.server.mcpserver import MCPServer
from pydantic import Field

import common
from common import program
from fastsandbox.models import McpServerCheck

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
    from types import TracebackType

    from starlette.types import ASGIApp, Receive, Scope, Send

    from fastsandbox import Client, Sandbox
    from fastsandbox.models import McpGateway

__all__ = [
    "SERVE_ARG",
    "CallOutcome",
    "HttpServer",
    "Registration",
    "SandboxClient",
    "Session",
    "check_gateway",
    "dummy_token",
    "gateway_url",
    "registered",
    "registered_remote",
    "remove_secret",
    "serve_if_requested",
    "set_secret",
    "stored_secret",
    "tools",
]

SERVE_ARG = "mcp-serve"
"""The argument with which `sbx` starts an example as the MCP server of the examples."""

SERVER_NAME = "fastsandbox-examples"
"""The name the MCP server of the examples gives in its handshake."""

SHUTDOWN_GRACE = 2
"""How long `HttpServer` lets open connections finish when it stops, in seconds.

The gateway may keep a stream open on its session: without a deadline, the
server would wait for it forever.
"""


def tools() -> MCPServer:
    """A few tools an agent can call to show that the server is reached.

    `sum`, `echo` and `host_time`, as the MCP server of the examples of
    `docker-sandbox` offers them. Each answers with text only, the way a
    terminal agent shows it.
    """
    # The SDK configures the logging of the process: warnings only, so that the
    # sessions the gateway opens do not drown what the example prints.
    server: MCPServer = MCPServer(SERVER_NAME, log_level="WARNING")

    @server.tool(name="sum", description="Add two numbers", structured_output=False)
    def add(
        a: Annotated[int, Field(description="First number.")],
        b: Annotated[int, Field(description="Second number.")],
    ) -> str:
        """Adds two numbers."""
        return str(a + b)

    @server.tool(
        name="echo", description="Send a text back, as seen by the host", structured_output=False
    )
    def echo(text: Annotated[str, Field(description="Text to send back.")]) -> str:
        """Sends the text back, marked as coming from the host."""
        return f"host says: {text}"

    @server.tool(
        name="host_time",
        description="Current time of the host, in seconds since the Unix epoch",
        structured_output=False,
    )
    def host_time() -> str:
        """Current time of the host, in seconds since the Unix epoch."""
        return str(int(time.time()))

    return server


def serve_if_requested() -> bool:
    """Serves the MCP tools on standard input and output when started with `SERVE_ARG`.

    Returns whether it did, in which case the program has nothing else to do.
    Call it first, before `common.main`: the server runs its own event loop,
    and nothing else may write to standard output, which carries the MCP
    session.
    """
    if sys.argv[1:2] != [SERVE_ARG]:
        return False
    tools().run("stdio")
    return True


class _BearerOnly:
    """An ASGI middleware that lets through the HTTP requests carrying a bearer token only.

    It counts the requests it lets through and those it refuses, and its token
    can be replaced while the server runs. The lifespan of the application,
    which starts the session manager of the MCP SDK, passes through.
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.expected = f"Bearer {token}".encode()
        self.authorized = 0
        self.refused = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        carried = dict(scope["headers"]).get(b"authorization", b"")
        # A comparison in constant time, as a server compares a real secret.
        if hmac.compare_digest(carried, self.expected):
            self.authorized += 1
            await self.app(scope, receive, send)
            return
        self.refused += 1
        body = b"unauthorized\n"
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"text/plain"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class _EmbeddedServer(uvicorn.Server):
    """A uvicorn server run inside an example, which leaves the signals to the example.

    uvicorn takes over Ctrl-C while it serves; an embedded server must not, so
    that Ctrl-C cancels the example, which then stops the server on its way
    out.
    """

    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        """Leaves the signal handlers of the example in place."""
        yield


class HttpServer:
    """The MCP tools over streamable HTTP on a loopback port of the host, for one bearer token.

    Requests that do not carry `Authorization: Bearer <token>` are answered
    `401 Unauthorized`. The token can be rotated while the server runs. Use it
    as an async context manager: the server listens inside the block, on a
    free port, and stops at its end.

    Example:
        >>> async with HttpServer(dummy_token()) as http:
        ...     print(http.url)
    """

    def __init__(self, token: str) -> None:
        """A server for the bearer token `token`, started by `async with`."""
        self._token = token
        self._auth: _BearerOnly | None = None
        self._server: _EmbeddedServer | None = None
        self._task: asyncio.Task[None] | None = None
        self._port = 0
        self._url = ""

    async def __aenter__(self) -> HttpServer:
        # The SDK protects a loopback server against DNS rebinding: requests
        # must name `127.0.0.1` or `localhost` in their `Host` header, as the
        # gateway does with the loopback URL it is given, and as the proxy of
        # a sandbox does with the requests it forwards to `host.docker.internal`.
        self._auth = _BearerOnly(tools().streamable_http_app(host="127.0.0.1"), self._token)
        # The socket is bound before the server starts, so that the URL is
        # known: port 0 takes a free port.
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        config = uvicorn.Config(
            self._auth,
            log_config=None,
            access_log=False,
            log_level="warning",
            timeout_graceful_shutdown=SHUTDOWN_GRACE,
        )
        self._server = _EmbeddedServer(config)
        self._task = asyncio.create_task(self._server.serve(sockets=[listener]))
        while not self._server.started:
            if self._task.done():
                # The server failed to start: its error is the one to report.
                await self._task
                raise common.ExampleError("the MCP server stopped before it started")
            await asyncio.sleep(0.01)
        self._port = port
        self._url = f"http://127.0.0.1:{port}/mcp"
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._server is None or self._task is None:
            return
        self._server.should_exit = True
        try:
            await asyncio.wait_for(asyncio.shield(self._task), timeout=SHUTDOWN_GRACE + 5)
        except TimeoutError:
            self._server.force_exit = True
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    @property
    def url(self) -> str:
        """The URL of the MCP endpoint, e.g. `http://127.0.0.1:41000/mcp`."""
        return self._url

    @property
    def port(self) -> int:
        """The loopback port it listens on."""
        return self._port

    def rotate_token(self, token: str) -> None:
        """Replaces the token: requests carrying the previous one are refused from now on."""
        self._started().expected = f"Bearer {token}".encode()

    @property
    def authorized(self) -> int:
        """The requests that carried the token so far."""
        return self._started().authorized

    @property
    def refused(self) -> int:
        """The requests refused so far for a missing or wrong token."""
        return self._started().refused

    def _started(self) -> _BearerOnly:
        """The middleware of the running server.

        Raises:
            RuntimeError: When the server was not started with `async with`.
        """
        if self._auth is None:
            raise RuntimeError("the MCP server is not started: use it with `async with`")
        return self._auth


class Registration:
    """An MCP server registered with `sbx mcp add`, removed with `remove`."""

    def __init__(self, name: str) -> None:
        """The registration of the server `name`, already made."""
        self._name = name

    @classmethod
    async def add(cls, client: Client, name: str) -> Registration:
        """Registers the running example, started with `SERVE_ARG`, as the server `name`.

        The server is checked against the MCP policy of the daemon first. `sbx`
        starts it with the Python of the running example, whose environment has
        the MCP SDK: `<python> <script> mcp-serve`.

        Raises:
            ExampleError: When the policy refuses the server or `sbx mcp add`
                fails.
        """
        command = _server_command()
        await _check(client, McpServerCheck.local(name, command))
        executable, *args = command
        # `--args` takes a list: one flag per argument.
        flags = [part for arg in args for part in ("--args", arg)]
        await _sbx(["mcp", "add", name, "--command", executable, *flags])
        print(f"registered the local MCP server {name}", file=sys.stderr)
        return cls(name)

    @classmethod
    async def add_remote(
        cls, client: Client, name: str, url: str, headers: Sequence[str] = ()
    ) -> Registration:
        """Registers the server at `url` as the remote server `name`, sent `headers`.

        Each header is `Name: value`, where `${placeholder}` is filled from the
        secret stored by `set_secret`. The server is checked against the MCP
        policy of the daemon first. A loopback URL needs `--skip-ssrf-check`,
        which is passed: the example trusts its own server.

        Raises:
            ExampleError: When the policy refuses the server or `sbx mcp add`
                fails.
        """
        await _check(client, McpServerCheck.remote(name, url))
        flags = [part for header in headers for part in ("--header", header)]
        await _sbx(["mcp", "add", name, "--url", url, "--skip-ssrf-check", *flags])
        print(f"registered the remote MCP server {name} at {url}", file=sys.stderr)
        return cls(name)

    @property
    def name(self) -> str:
        """The name of the server, to pass to `Sandbox.load_mcp_server`."""
        return self._name

    async def remove(self) -> None:
        """Removes the server with `sbx mcp rm`.

        Raises:
            ExampleError: When `sbx mcp rm` fails.
        """
        await _sbx(["mcp", "rm", self._name, "-f"])
        print(f"removed the MCP server {self._name}", file=sys.stderr)


@contextlib.asynccontextmanager
async def registered(client: Client, name: str) -> AsyncIterator[Registration]:
    """Registers the running example as the local server `name` for the block.

    See `Registration.add`; the registration is removed at the end of the
    block, also when it fails.
    """
    registration = await Registration.add(client, name)
    try:
        yield registration
    finally:
        await registration.remove()


@contextlib.asynccontextmanager
async def registered_remote(
    client: Client, name: str, url: str, headers: Sequence[str] = ()
) -> AsyncIterator[Registration]:
    """Registers the server at `url` as the remote server `name` for the block.

    See `Registration.add_remote`; the registration is removed at the end of
    the block, also when it fails.
    """
    registration = await Registration.add_remote(client, name, url, headers)
    try:
        yield registration
    finally:
        await registration.remove()


def dummy_token() -> str:
    """A dummy bearer token, different on every call: never a real credential."""
    return f"example-{secrets.token_hex(8)}"


async def set_secret(server: str, placeholder: str, value: str) -> None:
    """Stores `value` as the secret `mcp:<server>:<placeholder>` of `sbx`.

    `sbx` fills `${placeholder}` in the headers of the server with it when the
    gateway connects to the server; the value never enters the sandbox. A
    gateway already connected keeps the previous value: unload and load the
    server again for it to use a new one.

    Raises:
        ExampleError: When `sbx secret set` fails.
    """
    key = f"mcp:{server}:{placeholder}"
    await _sbx(["secret", "set", key, "-f"], stdin=value)
    print(f"stored the secret {key}", file=sys.stderr)


async def remove_secret(server: str, placeholder: str) -> None:
    """Removes the secret stored by `set_secret`, and its endpoint binding.

    The first time the secret is sent, `sbx` adds an entry
    `mcp:<server>:<placeholder>:endpoint` that binds it to the URL of the
    server and outlives the secret itself: both go. Removing a missing secret
    succeeds.

    Raises:
        ExampleError: When `sbx secret rm` fails.
    """
    key = f"mcp:{server}:{placeholder}"
    await _sbx(["secret", "rm", key, "-f"])
    await _sbx(["secret", "rm", f"{key}:endpoint", "-f"])
    print(f"removed the secret {key} and its endpoint binding", file=sys.stderr)


@contextlib.asynccontextmanager
async def stored_secret(server: str, placeholder: str, value: str) -> AsyncIterator[None]:
    """Stores `value` as the secret `mcp:<server>:<placeholder>` for the block.

    See `set_secret`; the secret and its endpoint binding are removed at the
    end of the block (`remove_secret`), also when it fails, whatever value it
    was given in between.
    """
    await set_secret(server, placeholder, value)
    try:
        yield
    finally:
        await remove_secret(server, placeholder)


@dataclass(frozen=True)
class CallOutcome:
    """The result of one tool call.

    Attributes:
        tool: The tool called.
        text: The text of the result.
        is_error: Whether the tool reported an error.
    """

    tool: str
    text: str
    is_error: bool = False

    def text_or_raise(self) -> str:
        """The text of the result.

        Raises:
            ExampleError: When the tool reported an error.
        """
        if self.is_error:
            raise common.ExampleError(f"the tool {self.tool} failed: {self.text}")
        return self.text


@dataclass(frozen=True)
class Session:
    """What an MCP client saw in one session with a server.

    Attributes:
        server: The name the server gave in its handshake.
        tools: The names of the tools offered when the session opened.
        calls: The calls made, in order.
        tools_after: The names of the tools offered once the calls were made: a
            call such as the `mcp-add` tool of the gateway changes them.
    """

    server: str = ""
    tools: list[str] = field(default_factory=list)
    calls: list[CallOutcome] = field(default_factory=list)
    tools_after: list[str] = field(default_factory=list)

    def tool(self, name: str) -> str | None:
        """The tool named `name`, or whose name ends with `_<name>`.

        A gateway may prefix the tools of each server with its name.
        """
        suffix = f"_{name}"
        return next((tool for tool in self.tools if tool == name or tool.endswith(suffix)), None)


class SandboxClient:
    """The MCP client of `programs/mcp_client.py`, copied into a sandbox.

    It talks to the gateway exactly as the agent of the sandbox would: from
    inside, through the proxy of the sandbox, which adds the credential of the
    gateway on the way.
    """

    def __init__(self, sandbox: Sandbox, command: Sequence[str]) -> None:
        """The client run in `sandbox` by `command`, once installed."""
        self._sandbox = sandbox
        self._command = list(command)

    @classmethod
    async def install(cls, sandbox: Sandbox) -> SandboxClient:
        """Copies the client into `sandbox`, where its Python runs it.

        Raises:
            SandboxError: When the client cannot be copied.
        """
        return cls(sandbox, await program.install(sandbox, "mcp_client"))

    async def list_tools(self, url: str) -> Session:
        """Opens a session with `url` and lists the tools.

        Raises:
            ExampleError: When the client cannot connect.
        """
        return await self.session(url, [])

    async def call(self, url: str, tool: str, arguments: Mapping[str, Any]) -> str:
        """Opens a session with `url`, calls `tool` with `arguments`, and returns its text.

        Raises:
            ExampleError: When the client cannot connect or the tool reports an
                error.
        """
        session = await self.session(url, [(tool, arguments)])
        if not session.calls:
            raise common.ExampleError("the client printed no result")
        return session.calls[0].text_or_raise()

    async def session(self, url: str, calls: Sequence[tuple[str, Mapping[str, Any]]]) -> Session:
        """Opens a session with `url` and makes `calls`, in order, in that session.

        Raises:
            ExampleError: When the client cannot connect or a call breaks the
                session; a tool reporting an error is a `CallOutcome` with
                `is_error` set.
        """
        command = [*self._command, url]
        for tool, arguments in calls:
            command += [tool, json.dumps(arguments)]
        output = await self._sandbox.exec(command)
        if not output.ok:
            raise common.ExampleError(f"the MCP client failed: {output.stderr.strip()}")
        lines = []
        for line in output.stdout.splitlines():
            with contextlib.suppress(ValueError):
                lines.append(json.loads(line))
        return _session(lines)


def gateway_url(gateway: McpGateway) -> str:
    """The URL of `gateway`, as the sandbox reaches it.

    Raises:
        ExampleError: When the gateway has no URL.
    """
    if not gateway.url:
        raise common.ExampleError("the gateway has no URL")
    return gateway.url


async def check_gateway(sandbox: Sandbox) -> None:
    """Calls the `sum` tool of the examples from inside `sandbox`, through its MCP gateway.

    It installs the client, then calls `sum` through the gateway, as the agent
    of the sandbox will.

    Raises:
        ExampleError: When the gateway lists no `sum` tool, or the tool
            answers wrongly.
        SandboxError: When the client cannot be installed.
    """
    client = await SandboxClient.install(sandbox)
    url = gateway_url(await sandbox.mcp_gateway())
    session = await client.list_tools(url)
    sum_tool = session.tool("sum")
    if sum_tool is None:
        raise common.ExampleError("the gateway lists no sum tool")
    answer = await client.call(url, sum_tool, {"a": 2, "b": 3})
    if answer != "5":
        raise common.ExampleError(f"the gateway answered sum(2, 3) = {answer}")
    print("checked from inside the sandbox: the gateway answers sum(2, 3) = 5", file=sys.stderr)


def _server_command() -> list[str]:
    """The command that starts the running example as the MCP server of the examples.

    Raises:
        ExampleError: When the example is not run from a script, or its path
            holds a comma, which `sbx mcp add --args` would split.
    """
    script = getattr(sys.modules["__main__"], "__file__", None)
    if script is None:
        raise common.ExampleError("the example must run from its script to serve MCP")
    path = str(Path(script).resolve())
    if "," in path:
        raise common.ExampleError(f"sbx mcp add cannot take a path holding a comma: {path}")
    return [sys.executable, path, SERVE_ARG]


async def _check(client: Client, server: McpServerCheck) -> None:
    """Checks `server` against the MCP policy of the daemon.

    Raises:
        ExampleError: When the policy refuses it.
    """
    check = await client.mcp.check_registration(server)
    if not check.allowed:
        raise common.ExampleError(f"the MCP policy of the daemon refuses the server {server.name}")


def _session(lines: Sequence[Any]) -> Session:
    """The session printed by the client, one JSON object per line."""
    server = ""
    listings: list[list[str]] = []
    calls: list[CallOutcome] = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        if isinstance(line.get("server"), str):
            server = line["server"]
        if isinstance(line.get("tools"), list):
            listings.append([tool for tool in line["tools"] if isinstance(tool, str)])
        if isinstance(line.get("tool"), str) and isinstance(line.get("result"), dict):
            result = line["result"]
            text = [
                block["text"]
                for block in result.get("content") or []
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            ]
            calls.append(
                CallOutcome(line["tool"], "\n".join(text), is_error=result.get("isError") is True)
            )
    return Session(
        server=server,
        tools=listings[0] if listings else [],
        calls=calls,
        tools_after=listings[-1] if len(listings) > 1 else [],
    )


async def _sbx(args: Sequence[str], stdin: str | None = None) -> None:
    """Runs the `sbx` CLI without prompts, writing `stdin` to it when given.

    Raises:
        ExampleError: When `sbx` cannot be run or fails.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "sbx",
            "--no-input",
            *args,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as error:
        raise common.ExampleError(f"cannot run sbx: {error}") from error
    _, stderr = await process.communicate(f"{stdin}\n".encode() if stdin is not None else None)
    if process.returncode != 0:
        # The arguments may name a secret, never hold its value: they are safe
        # to show.
        message = stderr.decode(errors="replace").strip()
        raise common.ExampleError(f"sbx {' '.join(args)} failed: {message}")
