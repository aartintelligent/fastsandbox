"""A web server in a shell sandbox, published on a port of the host and reached from it.

The server is the `serve` command of `common/programs/tools.py`, a script of
the Python standard library copied into the sandbox and started with an
interactive execution, which keeps it running until the sandbox goes. The
example publishes its port on a loopback port of the host, fetches the page
from the host, then unpublishes the port.

Run it with:

    just example shell-ports
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from typing import TYPE_CHECKING

import common
import fastsandbox
from common import kit, program
from fastsandbox.models import PortBinding

if TYPE_CHECKING:
    from fastsandbox import Interactive

SANDBOX_PORT = 8000
"""Port of the server inside the sandbox."""

START_TIMEOUT = 10.0
"""How long the server may take to listen, in seconds."""

ATTEMPTS = 20
"""How many times the published port is tried before giving up."""

RETRY_DELAY = 0.5
"""Pause between two attempts on the published port, in seconds."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    package = await kit.package(client, "shell")
    name = fastsandbox.unique_name("example-ports")
    # A port of the host unlikely to be taken, different for each run.
    host_port = 40_000 + os.getpid() % 20_000
    async with client.create(name, kit=package) as sandbox, sandbox.running():
        # The page, written into a directory created first: uploads need an
        # existing directory.
        await sandbox.exec(["mkdir", "-p", "/tmp/www"], check=True)
        await sandbox.write_file("/tmp/www/index.html", "<h1>served from a sandbox</h1>\n")

        # The server runs as long as its execution: until the sandbox goes.
        tools = await program.install(sandbox, "tools")
        server = await sandbox.attach([*tools, "serve", str(SANDBOX_PORT), "/tmp/www"])
        await wait_listening(server)

        published = await sandbox.publish(PortBinding.tcp(SANDBOX_PORT, host_port))
        host_ip = published[0].host_ip or "127.0.0.1"
        print(f"published sandbox port {SANDBOX_PORT} on {host_ip}:{host_port}")

        page = await fetch(host_port)
        print(page.splitlines()[-1] if page else "")

        await sandbox.unpublish(*published)
        print("unpublished")


async def wait_listening(server: Interactive) -> None:
    """Reads the output of `server` until it says that it listens.

    Raises:
        ExampleError: When it ends before, or does not listen in time.
    """
    started = ""
    chunks = aiter(server)
    try:
        async with asyncio.timeout(START_TIMEOUT):
            while "listening on" not in started:
                started += (await anext(chunks)).text
    except StopAsyncIteration:
        raise common.ExampleError("the server ended before listening") from None
    except TimeoutError:
        raise common.ExampleError("the server did not start") from None


async def fetch(port: int) -> str:
    """`GET /` on the loopback port `port`, retried while the published port is not ready.

    Until it is, the connection is refused or reset.

    Raises:
        ExampleError: When the server does not answer `200` in time.
    """
    for _ in range(ATTEMPTS):
        with contextlib.suppress(OSError):
            response = await get(port)
            if response.split()[1:2] == ["200"]:
                return response
        await asyncio.sleep(RETRY_DELAY)
    raise common.ExampleError("the server did not answer on the published port")


async def get(port: int) -> str:
    """One `GET /` on the loopback port `port`: the whole response, headers included."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        writer.write(b"GET / HTTP/1.0\r\nHost: localhost\r\n\r\n")
        await writer.drain()
        return (await reader.read()).decode(errors="replace")
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()


if __name__ == "__main__":
    common.main(main)
