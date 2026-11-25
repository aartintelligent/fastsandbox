"""SSH into a shell sandbox through the socket, with the SSH client of the system.

The daemon exposes SSH as an API: `POST /sandbox/{name}/ssh` turns the
connection into a tunnel to the SSH server of the sandbox, which greets with
`SSH-2.0-Go`. No network port is published and no client key is needed: the
socket is the boundary, and the server accepts the `none` method for any user,
`root` included. A program that relays this tunnel further must therefore
guard it as it guards the socket.

The example first reads the greeting of the server through the tunnel of the
library (`Sandbox.ssh_tunnel`). Then it runs `ssh` as `agent` and as `root`.
`sbx setup ssh` writes a `ProxyCommand` running `sbx ssh proxy` into the SSH
configuration of the user; this example writes nothing there: it runs `ssh`
with `-F /dev/null`, a temporary `known_hosts`, no key and no agent, and the
`ProxyCommand` of fastsandbox, `python -m fastsandbox ssh-proxy <sandbox>`,
which relays its standard input and output to the tunnel.

Run it with:

    just example shell-ssh
"""

from __future__ import annotations

import asyncio
import shlex
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import common
import fastsandbox
from common import kit

if TYPE_CHECKING:
    from fastsandbox import Sandbox

USERS = ("agent", "root")
"""The users the example logs in as."""

COMMAND = "id -un; pwd"
"""What the example runs over SSH."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    package = await kit.package(client, "shell")
    name = fastsandbox.unique_name("example-ssh")
    async with client.create(name, kit=package) as sandbox, sandbox.running():
        banner = await greeting(sandbox)
        if not banner.startswith("SSH-2.0-"):
            raise common.ExampleError(f"not an SSH server: {banner!r}")
        print(f"the tunnel reaches an SSH server: {banner}")

        # The known hosts of this run only, removed with it.
        work = Path(tempfile.mkdtemp(prefix="example-ssh-"))
        try:
            for user in USERS:
                answer = await ssh(work, sandbox.name, user, COMMAND)
                print(f"ssh {user}@{sandbox.name}: {', '.join(answer.splitlines())}")
        finally:
            shutil.rmtree(work, ignore_errors=True)


async def greeting(sandbox: Sandbox) -> str:
    """The first line the SSH server of `sandbox` sends through the tunnel of the library."""
    async with await sandbox.ssh_tunnel() as tunnel:
        received = b""
        while b"\n" not in received:
            data = await tunnel.read()
            if not data:
                break
            received += data
    return received.partition(b"\n")[0].decode(errors="replace").rstrip("\r")


async def ssh(work: Path, name: str, user: str, command: str) -> str:
    """Runs `command` as `user` in the sandbox `name` with the SSH client of the system.

    It goes through the `ProxyCommand` of fastsandbox, with no configuration,
    key or agent of the user, and the standard output of the command is
    returned.

    Raises:
        ExampleError: When `ssh` is not installed or fails.
    """
    # `ssh` runs the proxy command through a shell: quote its words.
    proxy = shlex.join([sys.executable, "-m", "fastsandbox", "ssh-proxy", name])
    options = {
        "ProxyCommand": proxy,
        "UserKnownHostsFile": str(work / "known_hosts"),
        "GlobalKnownHostsFile": "/dev/null",
        # The host key is new at each run: accept it, and keep it for this
        # run only.
        "StrictHostKeyChecking": "accept-new",
        "BatchMode": "yes",
        "IdentityAgent": "none",
        "IdentitiesOnly": "yes",
        "IdentityFile": "/dev/null",
        "ConnectTimeout": "20",
        "LogLevel": "ERROR",
    }
    arguments = ["-F", "/dev/null"]
    for key, value in options.items():
        arguments += ["-o", f"{key}={value}"]
    try:
        process = await asyncio.create_subprocess_exec(
            "ssh",
            *arguments,
            f"{user}@{name}",
            command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise common.ExampleError("cannot run ssh: is an SSH client installed?") from None
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise common.ExampleError(f"ssh {user}@{name}: {stderr.decode(errors='replace').strip()}")
    return stdout.decode()


if __name__ == "__main__":
    common.main(main)
