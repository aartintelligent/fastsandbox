"""The daemon event stream: the replay of recent state, then live events only.

The full subscription first replays recent state, which ends with a `sync`
event and lets a program build its view of the sandboxes; the live
subscription then gives the events that follow, here while a sandbox is
created, used and deleted.

Run it with:

    just example shell-events
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import common
import fastsandbox
from common import kit
from fastsandbox import SandboxError
from fastsandbox.models import EventKind

if TYPE_CHECKING:
    from fastsandbox import Stream
    from fastsandbox.models import DaemonEvent

DELETION_TIMEOUT = 10.0
"""How long the deletion event is awaited once the sandbox is deleted, in seconds."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    package = await kit.package(client, "shell")
    name = fastsandbox.unique_name("example-events")

    # The full subscription replays recent state first, up to a sync marker.
    replayed = 0
    async with await client.events.subscribe() as replay:
        async for event in replay:
            if event.is_sync:
                break
            replayed += 1
    print(f"{replayed} events replayed before the sync marker")

    # Subscribed before the sandbox exists, so that its creation is seen.
    events = await client.events.subscribe_live()
    follower = asyncio.create_task(follow(events, name))

    async with client.create(name, kit=package) as sandbox, sandbox.running():
        await sandbox.exec(["curl", "-sS", "-o", "/dev/null", "https://example.com"])

    # The deletion event arrives shortly after the deletion itself; the
    # follower is cancelled when it does not come in time.
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(follower, DELETION_TIMEOUT)


async def follow(events: Stream[DaemonEvent], name: str) -> None:
    """Prints the events about the sandbox `name`, until its deletion.

    The stream is closed when the follower ends, also when it is cancelled or
    the connection breaks.
    """
    async with events:
        try:
            async for event in events:
                if not event.is_about(name):
                    continue
                match event.kind:
                    case EventKind.SANDBOX_LIFECYCLE:
                        print(f"event: sandbox {event.action}")
                    case EventKind.SANDBOX_PORTS:
                        print(f"event: ports {event.action}")
                    case EventKind.POLICY_NETWORK:
                        print(f"event: network {event.action}")
                    case _:
                        print(f"event: {event.event_type} {event.action}")
                if event.action == "deleted":
                    return
        except SandboxError as error:
            # The example goes on without its events: they only illustrate it.
            print(f"event stream ended: {error}")


if __name__ == "__main__":
    common.main(main)
