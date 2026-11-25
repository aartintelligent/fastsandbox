"""A minimal MCP client over streamable HTTP, of the Python standard library alone.

It connects to a server, lists its tools, and calls some of them in one
session:

    python3 mcp_client.py <url> [<tool> <json arguments>]...
    python3 mcp_client.py http://mcp-gateway.docker.internal/mcp sum '{"a": 2, "b": 3}'

It prints one JSON object per line — `{"server": …}`, `{"tools": [...]}`, one
`{"tool": …, "result": …}` per call, then `{"tools": [...]}` again when a call
was made, since a call may change the tools of the session — so that a program
can read what it saw. The MCP examples copy it into a sandbox and run it
there, against the MCP gateway the agents of the sandbox use: its requests go
through the HTTP proxy of the sandbox (`HTTP_PROXY`, unless `NO_PROXY` names
the host), as those of an agent do, and the proxy adds the credential of the
gateway on the way.

It speaks the initialize handshake of the streamable HTTP transport: every
message is a `POST` to the URL, answered with JSON or with a stream of
server-sent events, and the session is the `Mcp-Session-Id` header of the
answer to `initialize`. It needs no package: the sandbox has Python, not the
MCP SDK, and its network may be closed to package indexes.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any

PROTOCOL_VERSION = "2025-06-18"
"""The protocol version the client asks for; the server answers the one it speaks."""

CLIENT_INFO = {"name": "fastsandbox-example-mcp-client", "version": "0.1.0"}
"""How the client introduces itself in the handshake."""

TIMEOUT = 120.0
"""Deadline of one request, in seconds: the gateway may start a server on the first one."""

USAGE = "usage: mcp_client.py <url> [<tool> <json arguments>]..."
"""How the program is called."""


class McpError(Exception):
    """A failure of the session: a broken connection, an HTTP error, or a JSON-RPC error."""


class Session:
    """An MCP session with the server at one URL."""

    def __init__(self, url: str) -> None:
        """A session with `url`, opened by `initialize`."""
        self.url = url
        self.session_id: str | None = None
        self.protocol: str | None = None
        self.server = ""
        self._next_id = 0

    def initialize(self) -> None:
        """Opens the session: the handshake, then the `initialized` notification."""
        result = self.request(
            "initialize",
            {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO},
        )
        self.protocol = result.get("protocolVersion")
        self.server = (result.get("serverInfo") or {}).get("name", "")
        self.notify("notifications/initialized")

    def tools(self) -> list[str]:
        """The names of the tools the session offers, every page of the listing."""
        names: list[str] = []
        cursor: str | None = None
        while True:
            result = self.request("tools/list", {"cursor": cursor} if cursor else {})
            names += [tool["name"] for tool in result.get("tools", [])]
            cursor = result.get("nextCursor")
            if not cursor:
                return names

    def call(self, tool: str, arguments: dict[str, Any]) -> Any:
        """The result of the tool `tool` called with `arguments`, as the server sent it."""
        return self.request("tools/call", {"name": tool, "arguments": arguments})

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Sends the request `method` and returns its result.

        Raises:
            McpError: When the server answers with an error, or not at all.
        """
        self._next_id += 1
        message = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        with self._send("POST", message) as response:
            if self.session_id is None:
                self.session_id = response.headers.get("Mcp-Session-Id")
            answer = _answer(response, self._next_id)
        if "error" in answer:
            error = answer["error"]
            raise McpError(f"{method}: {error.get('message', error)}")
        result = answer.get("result")
        return result if isinstance(result, dict) else {}

    def notify(self, method: str) -> None:
        """Sends the notification `method`, which the server acknowledges without an answer."""
        with self._send("POST", {"jsonrpc": "2.0", "method": method}):
            pass

    def close(self) -> None:
        """Ends the session on the server; a server that keeps sessions open may refuse."""
        if self.session_id is None:
            return
        try:
            with self._send("DELETE", None):
                pass
        except McpError:
            # The session ends with the process anyway.
            pass

    def _send(self, method: str, message: dict[str, Any] | None) -> Any:
        """Sends `message` with the headers of the session, and returns the open response.

        Raises:
            McpError: When the connection fails or the server answers an HTTP
                error.
        """
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.session_id is not None:
            headers["Mcp-Session-Id"] = self.session_id
        if self.protocol is not None:
            headers["MCP-Protocol-Version"] = self.protocol
        data = json.dumps(message).encode() if message is not None else None
        # `urlopen` goes through the proxy of `HTTP_PROXY`, unless `NO_PROXY`
        # names the host, as the agents of the sandbox do.
        request = urllib.request.Request(self.url, data=data, headers=headers, method=method)
        try:
            return urllib.request.urlopen(request, timeout=TIMEOUT)
        except urllib.error.HTTPError as error:
            body = error.read().decode(errors="replace").strip()
            raise McpError(f"{method} {self.url}: HTTP {error.code} {body}") from None
        except OSError as error:
            raise McpError(f"{method} {self.url}: {error}") from None


def _answer(response: Any, request_id: int) -> dict[str, Any]:
    """The JSON-RPC answer to the request `request_id` in `response`.

    A plain JSON body is the answer; a stream of server-sent events may carry
    notifications and requests of the server first, which a client that offers
    no capability ignores.

    Raises:
        McpError: When the response holds no answer to the request.
    """
    if response.headers.get_content_type() != "text/event-stream":
        answer = json.loads(response.read() or b"{}")
        if isinstance(answer, dict):
            return answer
        raise McpError("the server answered with something else than a JSON-RPC message")
    data: list[str] = []
    for raw in response:
        line = raw.decode().rstrip("\r\n")
        if line.startswith("data:"):
            data.append(line[5:].removeprefix(" "))
            continue
        if line or not data:
            continue
        # A blank line ends an event: its data lines form one message.
        message = json.loads("\n".join(data))
        data = []
        if isinstance(message, dict) and message.get("id") == request_id:
            return message
    raise McpError("the event stream ended without an answer")


def main(argv: list[str]) -> int:
    """Runs the client on its command line, and returns its exit code."""
    if not argv or len(argv[1:]) % 2:
        print(USAGE, file=sys.stderr)
        return 2
    url, pairs = argv[0], argv[1:]
    calls = []
    for tool, text in zip(pairs[::2], pairs[1::2], strict=True):
        arguments = json.loads(text)
        if not isinstance(arguments, dict):
            print(f"the arguments of {tool} are not a JSON object", file=sys.stderr)
            return 2
        calls.append((tool, arguments))

    session = Session(url)
    try:
        session.initialize()
        _print({"server": session.server})
        _print({"tools": session.tools()})
        for tool, arguments in calls:
            _print({"tool": tool, "result": session.call(tool, arguments)})
        if calls:
            _print({"tools": session.tools()})
    except McpError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    finally:
        session.close()
    return 0


def _print(line: dict[str, Any]) -> None:
    """Prints one line of what the client saw, as compact JSON."""
    print(json.dumps(line, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
