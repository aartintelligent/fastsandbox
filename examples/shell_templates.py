"""A shell sandbox saved as an image, a new sandbox started from it, the image moved as a file.

The example works as `sbx template save`, `sbx create -t` and
`sbx template load` do. The first sandbox gets a file, is stopped and saved
(`Sandbox.save`); the second starts from the saved image (the `template` of its
creation request, with `PullPolicy.NEVER`: the image is on this host only), its
request stored as JSON and replayed, and finds the file. The image is then
exported to `target/templates/` of the repository, removed, and loaded back
from the file (`Images.load_file`), the way a template moves to another host.
The image and the file are removed at the end, also on an error.

Run it with:

    just example shell-templates
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import common
import fastsandbox
from common import kit
from fastsandbox import CreateRequest
from fastsandbox.models import PullPolicy

if TYPE_CHECKING:
    from fastsandbox import Client, KitPackage

EXPORTS = Path(__file__).resolve().parent.parent / "target" / "templates"
"""Directory of the exported images, in the build output of the repository."""

SAVED_FILE = "/home/agent/saved.txt"
"""The file the first sandbox holds when it is saved."""

SAVED_TEXT = "written before the save\n"
"""What that file says."""

MIB = 1 << 20
"""Bytes in a mebibyte."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    package = await kit.package(client, "shell")
    tag = f"example-snapshot-{os.getpid()}:v1"
    archive = EXPORTS / f"example-snapshot-{os.getpid()}.tar"
    try:
        await run(client, package, tag, archive)
    finally:
        # Whatever happened, the image and its file go.
        if await client.images.exists(tag):
            await client.images.remove(tag)
            print(f"removed the image {tag}")
        remove_file(archive)


async def run(client: Client, package: KitPackage, tag: str, archive: Path) -> None:
    """Saves a sandbox as `tag`, creates another from it, then moves the image through `archive`.

    Raises:
        ExampleError: When the new sandbox lacks the saved file, or the image
            does not go and come back.
    """
    first = fastsandbox.unique_name("example-template-source")
    async with client.create(first, kit=package) as sandbox:
        async with sandbox.running():
            await sandbox.write_file(SAVED_FILE, SAVED_TEXT)
        # A sandbox is saved stopped, its file system at rest.
        await sandbox.stop()
        saved = await sandbox.save(tag)
    print(f"saved {first} as {saved.tag} ({saved.image_id})")

    # A creation request is plain data: an application can store it, as JSON
    # in its database for instance, and replay it under another name.
    stored = (
        package.request("{{name}}")
        .model_copy(update={"template": tag, "pull_policy": PullPolicy.NEVER})
        .model_dump_json()
    )
    second = fastsandbox.unique_name("example-template-copy")
    request = CreateRequest.model_validate_json(stored)
    async with client.create(second, kit=package, request=request) as sandbox, sandbox.running():
        text = (await sandbox.exec(["cat", SAVED_FILE], check=True)).stdout
        common.expect(text == SAVED_TEXT, f"the new sandbox holds {text!r}")
        print(f"{sandbox.name} starts from the image and holds {SAVED_FILE}")

    # The way a template moves to another host: a file, loaded there.
    images = client.images
    data = await images.export(tag)
    write_bytes(archive, data)
    print(f"exported to a file of {len(data) // MIB} MiB")
    await images.remove(tag)
    common.expect(not await images.exists(tag), "the image is still there")
    print("image removed from the daemon")
    await images.load_file(archive)
    common.expect(await images.exists(tag), "the image did not come back")
    print(f"loaded back from the file: {tag} is there again")


def write_bytes(path: Path, data: bytes) -> None:
    """Writes `data` to the file `path` of the host, creating its directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def remove_file(path: Path) -> None:
    """Removes the file `path` of the host, if it exists."""
    path.unlink(missing_ok=True)


if __name__ == "__main__":
    common.main(main)
