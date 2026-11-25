"""The first steps with fastsandbox: connect, look around, create, run, delete.

The example connects to the daemon of the current user, lists the sandboxes
and counts the images it holds, creates a sandbox of the `shell` kit, runs a
command in it, and deletes it.

Run it with:

    just example base
"""

from __future__ import annotations

import common
import fastsandbox
from common import kit


async def main() -> None:
    """Runs the example."""
    # One client per program: the handles taken from it share its connection.
    client = await common.connect()
    for existing in await client.sandboxes.list():
        print(f"sandbox {existing.name:<30} {existing.status:<8} {existing.agent}")
    print(f"{len(await client.images.list())} images held by the daemon")

    # A sandbox of the `shell` kit, created from a package compiled once; the
    # `async with` block deletes it on the way out, whatever happens.
    package = await kit.package(client, "shell")
    async with (
        client.create(fastsandbox.unique_name("example-base"), kit=package) as sandbox,
        # The daemon stops a sandbox 30 seconds after its last session: hold
        # one for as long as the sandbox is used.
        sandbox.running(),
    ):
        info = await sandbox.inspect()
        print(f"{info.name} is {info.status} (id {info.id})")

        output = await sandbox.exec(["uname", "-a"], check=True)
        print(output.stdout, end="")


if __name__ == "__main__":
    common.main(main)
