"""The tools the examples run inside a sandbox: a web server and an HTTP client.

A sandbox runs Linux, whatever the host, and an example checks what happens in
there: a page served on a published port, the secrets the proxy of the sandbox
writes into requests. This script does both, with the Python standard library
alone; `common.program.install(sandbox, "tools")` copies it into the sandbox:

- `serve <port> <directory>` serves the files of `<directory>` on `<port>` of
  every interface, and prints `listening on <port>` once it listens;
- `get <url> [<header> <value>]...` sends `GET <url>`, plain HTTP, with the
  given headers, through the proxy of the sandbox (`HTTP_PROXY`, unless
  `NO_PROXY` names the host), and prints the body of a successful answer.

Failures exit with code 1 and a message on standard error.

    python3 /tmp/example-tools.py serve 8000 /tmp/www
    python3 /tmp/example-tools.py get http://postman-echo.com/headers Authorization "Bearer …"
"""

from __future__ import annotations

import functools
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

USAGE = "usage: tools.py serve <port> <directory> | get <url> [<header> <value>]..."
"""How the program is called, printed for unknown arguments."""

AGENT = "fastsandbox-examples"
"""User agent of the requests: some services refuse anonymous clients."""

TIMEOUT = 30.0
"""Deadline of a request, in seconds."""


class _QuietHandler(SimpleHTTPRequestHandler):
    """Serves the files of a directory without logging every request."""

    def log_message(self, format: str, *args: Any) -> None:
        """Logs nothing: the example reads the standard output of the server."""


def serve(port: str, directory: str) -> None:
    """Serves the files of `directory` on `port` until the process is stopped.

    A directory answers with its `index.html`, a missing file with
    `404 Not Found`; a path that would leave `directory` is refused by the
    handler of the standard library.
    """
    handler = functools.partial(_QuietHandler, directory=directory)
    with ThreadingHTTPServer(("0.0.0.0", int(port)), handler) as server:
        # The example waits for this line: flush it, since the output of the
        # execution is a pipe, not a terminal.
        print(f"listening on {port}", flush=True)
        server.serve_forever()


def get(url: str, headers: list[tuple[str, str]]) -> None:
    """Sends `GET url` with `headers`, and prints the body of a successful answer.

    `urllib` reads the proxy from `HTTP_PROXY` (or `http_proxy`) and skips it
    for the hosts `NO_PROXY` (or `no_proxy`) names: through the proxy, the
    request names the whole URL, which is how the proxy of the sandbox sees
    and rewrites it.

    Raises:
        SystemExit: When the URL is not plain HTTP, or the answer is not a
            success.
    """
    if urllib.parse.urlsplit(url).scheme != "http":
        raise SystemExit(f"{url}: only http:// URLs are supported")
    request = urllib.request.Request(url, headers={"User-Agent": AGENT, **dict(headers)})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        raise SystemExit(f"{url}: {error.code} {error.reason}") from None
    except OSError as error:
        raise SystemExit(f"{url}: {error}") from None
    sys.stdout.write(body.decode(errors="replace"))


def main(args: list[str]) -> None:
    """Runs the command `args` names.

    Raises:
        SystemExit: With the usage, for unknown arguments.
    """
    match args:
        case ["serve", port, directory]:
            serve(port, directory)
        case ["get", url, *rest] if len(rest) % 2 == 0:
            get(url, list(zip(rest[::2], rest[1::2], strict=True)))
        case _:
            raise SystemExit(USAGE)


if __name__ == "__main__":
    main(sys.argv[1:])
