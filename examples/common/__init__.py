"""What the fastsandbox examples share.

Each example shows one use of the library; the plumbing they all need lives
here, so that their own code stays about the library:

- `connect` reaches the daemon of the current user, `main` runs an example
  and reports its failure in one line, `expect` fails it when a check does
  not hold, and `report_withheld` prints the credentials the daemon withholds
  from a sandbox it created;
- `kit.package` forges a kit without the `sbx` CLI, or compiles it with the
  CLI when asked, through the kit cache of the library, and says so;
- `terminal.relay` plugs the local terminal into an interactive session, and
  `host` gives an agent session what `sbx run` passes from the host;
- `program.install` copies a program of `programs/` into a sandbox;
- `mcp` serves the MCP tools of the examples, registers them with `sbx`, and
  checks a gateway from inside a sandbox;
- `agent` runs a coding agent, with or without that server;
- `automation` runs one unattended on a task, and checks its work.

The examples run from the repository root with `just example <name>`, which
puts `examples/` first on the module path: they import this package as
`common`.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import fastsandbox

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from fastsandbox.models import Created

__all__ = ["ExampleError", "connect", "expect", "main", "report_withheld"]


class ExampleError(Exception):
    """A check of an example that does not hold: the daemon did not do what it showed."""


def expect(condition: bool, message: str) -> None:
    """Fails the example with `message` unless `condition` holds.

    Raises:
        ExampleError: When `condition` is false.
    """
    if not condition:
        raise ExampleError(message)


async def connect() -> fastsandbox.Client:
    """Connects to the daemon of the current user and reports its version.

    Raises:
        DaemonUnavailableError: When the daemon is not running.
        UnsupportedVersionError: When it speaks an API version the library was
            not audited on.
    """
    client = await fastsandbox.connect()
    health = client.health
    print(f"sandboxd {health.version} (API {health.api_version})", file=sys.stderr)
    return client


def report_withheld(created: Created | None) -> None:
    """Prints the credentials the daemon withholds from the sandbox it just created, if any.

    A kit declares the credential of its agent (`anthropic` for `claude`, …),
    and the daemon gives the sandbox its value only when it authorizes it: it
    does for a package the forge or the `sbx` CLI made. One it withholds gets
    nothing from the proxy, a value pushed later included. `created` is what
    the creation answered (`Creation.created`).
    """
    if created is not None and created.withheld:
        print(
            f"the daemon withholds the credentials the kits declare: {', '.join(created.withheld)}",
            file=sys.stderr,
        )


def main(example: Callable[[], Coroutine[Any, Any, None]]) -> None:
    """Runs `example` and exits with its outcome.

    A failure of the library, or a check of the example that does not hold
    (`ExampleError`), is reported in one line, with exit code 1; Ctrl-C
    ends the example with exit code 130, once the sandboxes it created are
    deleted: `asyncio` cancels the example, and the `async with` blocks of its
    sandboxes delete them on the way out.
    """
    try:
        fastsandbox.run(example())
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130) from None
    except fastsandbox.DaemonUnavailableError as error:
        print(
            f"error: cannot reach sandboxd, is Docker Sandboxes (sbx) installed and running? "
            f"({error})",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except (fastsandbox.SandboxError, ExampleError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from None
