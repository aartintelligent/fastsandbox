"""A mixin kit added to running shell sandboxes: installed in place, or by a container swap.

The mixin of the examples (`examples/kits/example-mixin/spec.yaml`) writes a
marker file when it is installed. Its `spec.yaml` is written in YAML, which
only the `sbx` CLI reads: the example asks the CLI (`sbx=True`), which compiles
it once with the `shell` base kit, as a package of both. Each sandbox is
created from the `shell` kit alone, given some work in progress, then gets the
mixin from that package:

- **in place** (`KitPackage.install_into`): the install command runs in the
  running container. Fast, but the kit list of the sandbox stays as it was,
  so a recreation of the container would lose the kit;
- **by a swap** (`KitPackage.add_to`): the daemon commits the container to an
  image, then recreates it with the longer kit list. The work in progress is
  kept, the sandbox keeps its identity, and the kit list now holds the mixin.

A third sandbox gets both changes by hand, from the parts of the package (its
kit artifacts and references, the agent its base kit describes, its images)
and the two routes of the daemon (`Sandbox.add_kit_artifact`,
`Sandbox.swap_container`): what a program does to compose kits itself.

Run it with:

    just example shell-kits
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import common
import fastsandbox
from common import kit
from fastsandbox import KitAgent
from fastsandbox.models import SwapRequest

if TYPE_CHECKING:
    from fastsandbox import Client, KitPackage, Sandbox

MIXIN = Path(__file__).resolve().parent / "kits" / "example-mixin"
"""The mixin kit of the examples."""

MARKER = "/home/agent/example-mixin.txt"
"""The file the mixin writes when it is installed."""

WORK = "/home/agent/work-in-progress.txt"
"""Work in progress, written before the kit changes."""

KITS_LABEL = "com.docker.sandbox.kits"
"""Label of a sandbox that lists its kits, as a JSON array of references."""


@dataclass(frozen=True)
class State:
    """What the example compares before and after a kit change.

    Attributes:
        id: Identifier of the sandbox.
        kits: Number of kits the sandbox lists.
        marker: Whether the marker of the mixin is there.
    """

    id: str
    kits: int
    marker: bool


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    base = await kit.package(client, "shell", sbx=True)
    mixed = await kit.package(client, "shell", mixins=[MIXIN], sbx=True)
    await in_place(client, base, mixed)
    await by_swap(client, base, mixed)
    await by_hand(client, base, mixed)


async def in_place(client: Client, base: KitPackage, mixed: KitPackage) -> None:
    """Installs the mixin of `mixed` in place, in a running sandbox of `base`."""
    name = fastsandbox.unique_name("example-kits-in-place")
    async with client.create(name, kit=base) as sandbox, sandbox.running():
        before = await prepare(sandbox)
        installed = await mixed.install_into(sandbox)
        after = await state(sandbox)
        print(
            f"in place: {installed} mixin installed, marker {presence(after.marker)}, "
            f"same sandbox: {after.id == before.id}, "
            f"kits listed: {before.kits} then {after.kits}"
        )
        common.expect(after.marker, "the mixin did not run")
        common.expect(after.kits == before.kits, "the kit list changed")


async def by_swap(client: Client, base: KitPackage, mixed: KitPackage) -> None:
    """Adds the mixin of `mixed` to a sandbox of `base` by a swap of its container."""
    name = fastsandbox.unique_name("example-kits-swap")
    async with client.create(name, kit=base) as sandbox:
        async with sandbox.running():
            before = await prepare(sandbox)
            outcome = await mixed.add_to(sandbox)
            print(
                "container swapped: the previous one committed to "
                f"{outcome.committed_image_id or 'an image'}"
            )
        # The new container needs a session of its own.
        async with sandbox.running():
            after = await state(sandbox)
            work = (await sandbox.exec(["cat", WORK])).ok
            print(
                f"by a swap: marker {presence(after.marker)}, "
                f"work in progress {'kept' if work else 'lost'}, "
                f"same sandbox: {after.id == before.id}, "
                f"kits listed: {before.kits} then {after.kits}"
            )
            common.expect(after.marker, "the mixin did not run")
            common.expect(work, "the work in progress was lost")
            common.expect(after.kits == before.kits + 1, "the kit list did not grow")


async def by_hand(client: Client, base: KitPackage, mixed: KitPackage) -> None:
    """Makes the same two changes by hand, from the parts of the package.

    Its kit artifacts and references, its images, then the two routes of the
    daemon: an artifact installed in place, and a swap with the complete kit
    list.
    """
    artifacts = mixed.kit_artifacts
    refs = mixed.kit_refs
    agent = KitAgent.from_artifact(artifacts[0])
    if agent is None:
        raise common.ExampleError("the base kit has no manifest")
    print(
        f"the package holds {len(refs)} kits, base first: "
        f"agent {agent.name} ({agent.binary or 'no program'}), then {', '.join(refs[1:])}"
    )
    name = fastsandbox.unique_name("example-kits-by-hand")
    async with client.create(name, kit=base) as sandbox:
        async with sandbox.running():
            before = await prepare(sandbox)
            # The images of the mixin first: the daemon resolves nothing itself.
            await mixed.load_images(sandbox.client)
            await sandbox.add_kit_artifact(artifacts[1])
            common.expect((await state(sandbox)).marker, "the mixin did not run")
            print("by hand, in place: the artifact of the mixin installed")

            request = SwapRequest(
                docker_name_override=f"{sandbox.name}-swap-by-hand",
                kit_artifacts=artifacts,
                kit_refs=refs,
            )
            await sandbox.swap_container(request)
        async with sandbox.running():
            after = await state(sandbox)
            common.expect(after.kits == before.kits + 1, "the kit list did not grow")
            print(f"by hand, by a swap: the complete kit list, {after.kits} kits listed")


async def prepare(sandbox: Sandbox) -> State:
    """Writes the work in progress, and checks that the mixin is not there yet.

    Returns the state of the sandbox before the kit change.
    """
    await sandbox.write_file(WORK, "half done\n")
    current = await state(sandbox)
    common.expect(not current.marker, "the mixin is there too early")
    return current


async def state(sandbox: Sandbox) -> State:
    """The identifier, kit count and marker of `sandbox`."""
    info = await sandbox.inspect()
    listed = info.labels.get(KITS_LABEL)
    if listed is None:
        raise common.ExampleError("the sandbox lists no kits")
    try:
        kits = json.loads(listed)
    except ValueError:
        raise common.ExampleError("the kit list is not a JSON array") from None
    marker = (await sandbox.exec(["test", "-e", MARKER])).ok
    return State(id=info.id, kits=len(kits), marker=marker)


def presence(present: bool) -> str:
    """`there` or `absent`."""
    return "there" if present else "absent"


if __name__ == "__main__":
    common.main(main)
