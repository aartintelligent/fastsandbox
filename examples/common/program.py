"""Programs of `programs/` run inside a sandbox.

A sandbox runs Linux, whatever the host, and the `shell` kit ships Python 3:
the programs the examples run in there are scripts of the Python standard
library alone, copied into the sandbox with `Sandbox.write_file` and started
with an execution. Nothing is built or installed, and they need no network.
The MCP examples install their MCP client this way (`programs/mcp_client.py`),
`shell-ports` and `shell-secrets` the web server and the HTTP client of
`programs/tools.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastsandbox import Sandbox

__all__ = ["PROGRAMS", "install"]

PROGRAMS = Path(__file__).parent / "programs"
"""The directory of the programs run inside sandboxes."""


async def install(sandbox: Sandbox, program: str) -> list[str]:
    """Copies `programs/<program>.py` into `sandbox`, and returns the command that runs it.

    The script goes to `/tmp/example-<program>.py`, readable by every user of
    the sandbox; the command runs it with the `python3` of the sandbox.

    Raises:
        FileNotFoundError: When `programs/` has no such program.
    """
    path = f"/tmp/example-{program}.py"
    await sandbox.write_file(path, (PROGRAMS / f"{program}.py").read_bytes(), mode=0o755)
    print(f"{program} copied into the sandbox", file=sys.stderr)
    return ["python3", path]
