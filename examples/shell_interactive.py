"""An interactive shell in a sandbox, relayed to the local terminal.

Keys go to the shell, its output comes back, and resizing the window resizes
its terminal; `common.terminal` does the relaying. Leave it with `exit`. The
sandbox is deleted when the shell ends.

Run it with:

    just example shell-interactive
"""

from __future__ import annotations

import sys

import common
import fastsandbox
from common import kit, terminal


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    package = await kit.package(client, "shell")
    async with (
        client.create(fastsandbox.unique_name("example-interactive"), kit=package) as sandbox,
        sandbox.running(),
    ):
        # A login shell, which reads the profile of the kit, in a terminal of
        # the size of the local window.
        session = await sandbox.attach(["bash", "-l"], tty=True, size=terminal.size())
        code = await terminal.relay(session)
        print(f"shell exited with code {code}", file=sys.stderr)


if __name__ == "__main__":
    common.main(main)
