"""The life of a shell sandbox step by step, with the errors a program meets on the way.

Each error has its own class, so that a program tells them apart:

- A creation with an unknown governance profile is refused before anything is
  created (`InvalidInputError`).
- The creation is followed as it happens (`client.sandboxes.create_stream`),
  with a port published from the start, the shared skills store turned off and
  the credential bindings file of the host recorded, as the CLI does; a failure
  would come as an item of that stream.
- A sandbox that does not exist is `NotFoundError`; a command in a stopped
  sandbox is `ConflictError`.
- A session (`Sandbox.hold_session`) keeps the sandbox running once it is
  started (`Sandbox.start`); the daemon stops it about 30 seconds after the
  last session closes.
- The port published from the start is part of the *desired* configuration:
  replacing it there changes nothing until the next start. A UDP port is
  published and unpublished on a running sandbox.
- The working directory is recorded.
- The deletion names the identifier returned at creation: a deletion that names
  another one is refused, so that a program never deletes a sandbox recreated
  under the same name by someone else.

The sandbox is deleted at the end, also on an error or Ctrl-C.

Run it with:

    just example shell-lifecycle
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import TYPE_CHECKING

import common
import fastsandbox
from common import kit
from fastsandbox import ConflictError, NotFoundError, PortBinding
from fastsandbox.exceptions import InvalidInputError
from fastsandbox.models import (
    CreateFailure,
    CreateProgress,
    CreateResult,
    CreateUnknown,
    SkillsMode,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fastsandbox import Client, KitPackage, Sandbox
    from fastsandbox.models import Created

SANDBOX_PORT = 8080
"""Port of the sandbox published from the start."""

UDP_PORT = 5353
"""UDP port of the sandbox published while it runs."""

WORKING_DIR = "/tmp"
"""Working directory recorded for the sandbox."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    package = await kit.package(client, "shell")
    name = fastsandbox.unique_name("example-lifecycle")
    try:
        await run(client, package, name)
    finally:
        # The example deletes its sandbox itself; this is for an early exit.
        with contextlib.suppress(NotFoundError):
            await client.sandbox(name).force_delete()


async def run(client: Client, package: KitPackage, name: str) -> None:
    """Runs the life of the sandbox `name`.

    Raises:
        ExampleError: When the daemon does not behave as the example expects.
    """
    # Host ports of this run, apart from those of another run.
    base_port = 40_000 + os.getpid() % 20_000
    sandbox = client.sandbox(name)
    await refused_creation(client, package, name)
    created = await streamed_creation(client, package, name, base_port)

    try:
        await client.sandbox("example-no-such-sandbox").inspect()
    except NotFoundError as error:
        print(f"a sandbox that does not exist: not found (code {error.code or 'none'})")

    # A sandbox runs right after its creation, until about 30 seconds after its
    # last session; stopped at once here.
    info = await sandbox.stop()
    common.expect(not info.is_running, "still running")
    print(f"stopped: {info.status}")
    await stopped_command(sandbox)

    # A session keeps the sandbox running once started.
    session = await sandbox.hold_session()
    info = await sandbox.start()
    common.expect(info.is_running, "not running")
    print(f"started: {info.status}, session open: {session.is_connected}")
    await port_changes(sandbox, base_port)
    await sandbox.set_working_dir(WORKING_DIR)
    info = await sandbox.inspect()
    print(f"working directory recorded: {info.working_dir or '(none)'}")
    session.release()
    await guarded_deletion(sandbox, created.id)


async def refused_creation(client: Client, package: KitPackage, name: str) -> None:
    """Creates `name` with an unknown governance profile, which the daemon refuses.

    It refuses it before creating anything.

    Raises:
        ExampleError: When the creation succeeds, or leaves a sandbox behind.
    """
    refused = package.request(name).model_copy(update={"profile": "example-no-such-profile"})
    try:
        await package.create_with(client, refused)
    except InvalidInputError as error:
        message = str(error)
    else:
        raise common.ExampleError("a creation with an unknown profile succeeded")
    common.expect(await client.sandboxes.find(name) is None, "the refused sandbox exists")
    print(f"unknown profile: refused as invalid input, nothing created ({message})")


async def streamed_creation(
    client: Client, package: KitPackage, name: str, host_port: int
) -> Created:
    """Creates `name` with a port published from the start and no skills store.

    The creation is followed as it happens.

    Raises:
        ExampleError: When the creation fails, or its stream ends early.
    """
    request = package.request(name).with_port(PortBinding.tcp(SANDBOX_PORT, host_port))
    request = request.model_copy(update={"skills": SkillsMode.OFF})
    # The CLI records the file of the credentials the user approved for
    # third-party kits; built-in kits need none.
    if home := os.environ.get("HOME"):
        bindings = Path(home) / ".config/sbx/credentials.yaml"
        request = request.model_copy(update={"bindings_path": os.fspath(bindings)})

    # The stream creates from loaded images: the package loads its own first.
    loaded = await package.load_images(client)
    print(f"{loaded} kit archives loaded, the others already on the daemon")
    progress = 0
    created: Created | None = None
    async with await client.sandboxes.create_stream(request) as events:
        async for event in events:
            match event:
                case CreateProgress(message=message):
                    progress += 1
                    print(f"  creating: {message}")
                case CreateResult(created=result):
                    created = result
                    break
                # A failure comes as an item of the stream, the answer of the
                # daemon being HTTP 200.
                case CreateFailure(message=message):
                    raise common.ExampleError(f"creation failed: {message}")
                case CreateUnknown(raw=raw):
                    print(f"  unknown line: {raw}")
    if created is None:
        raise common.ExampleError("the creation stream ended early")
    print(
        f"created {created.name} (id {created.id}), {created.status}, "
        f"after {progress} progress lines"
    )
    return created


async def port_changes(sandbox: Sandbox, base_port: int) -> None:
    """Replaces the desired port, then publishes and unpublishes a UDP port.

    The desired port applies at the next start; the UDP port is published on
    the running sandbox.
    """
    print(f"published from the start: {ports(await sandbox.ports())}")
    old = PortBinding.tcp(SANDBOX_PORT, base_port)
    new = PortBinding.tcp(SANDBOX_PORT, base_port + 1)
    await sandbox.replace_desired_port(old, new)
    print(f"desired port replaced, published now: {ports(await sandbox.ports())}")
    await sandbox.stop()
    await sandbox.start()
    print(f"after a stop and a start: {ports(await sandbox.ports())}")

    udp = PortBinding.udp(UDP_PORT, base_port + 2, host_ip="127.0.0.1")
    published = await sandbox.publish(udp)
    print(f"UDP published: {ports(published)}")
    await sandbox.unpublish(*published)
    print(f"UDP unpublished: {ports(await sandbox.ports())}")


async def guarded_deletion(sandbox: Sandbox, sandbox_id: str) -> None:
    """Deletes `sandbox` naming another identifier, refused, then its own `sandbox_id`.

    Raises:
        ExampleError: When the first deletion succeeds, or the second leaves
            the sandbox behind.
    """
    try:
        await sandbox.delete(force=True, expected_id="not-the-id-of-the-sandbox")
    except ConflictError as error:
        print(
            f"deletion with another identifier: refused as a conflict (code {error.code or 'none'})"
        )
    else:
        raise common.ExampleError("a deletion with another identifier succeeded")
    await sandbox.delete(force=True, expected_id=sandbox_id)
    common.expect(not await sandbox.exists(), "the sandbox is still there")
    print("deleted with its own identifier")


async def stopped_command(sandbox: Sandbox) -> None:
    """Runs a command in the stopped sandbox, which the daemon refuses.

    Raises:
        ExampleError: When the command runs.
    """
    try:
        await sandbox.exec(["true"])
    except ConflictError as error:
        print(
            "a command in a stopped sandbox: conflict, worth retrying once it runs: "
            f"{error.transient}"
        )
    else:
        raise common.ExampleError("a command ran in a stopped sandbox")


def ports(bindings: Sequence[PortBinding]) -> str:
    """`bindings` as `host:port->sandbox_port/protocol` items."""
    if not bindings:
        return "none"
    return ", ".join(
        f"{port.host_ip or '*'}:{port.host_port}->{port.sandbox_port}/{port.protocol or 'tcp'}"
        for port in bindings
    )


if __name__ == "__main__":
    common.main(main)
