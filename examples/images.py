"""The images the daemon holds, as a program manages them.

The example lists the images, pulls one while following its progress, pulls it
again waiting for the outcome, reads its details, and shows what an unknown
image gives.

The image pulled is the one of the `shell` kit, `docker.io/sbx/shell`, as `sbx`
pulls it. When its `latest` tag was not on the daemon before, the example
removes the tag at the end, so that the daemon holds what it held. Saving a
sandbox as an image, exporting and loading it are in `shell-templates`.

Run it with:

    just example images
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import common
from fastsandbox import NotFoundError

if TYPE_CHECKING:
    from fastsandbox import Images

KIT_IMAGE = "docker.io/sbx/shell:latest"
"""The image pulled by the example, as `sbx` pulls the `shell` kit."""

UNKNOWN = "example-no-such-image:latest"
"""An image that does not exist."""

LISTED = 5
"""Images listed, out of all the daemon holds."""

MIB = 1 << 20
"""Bytes in a mebibyte."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    images = client.images
    await list_images(images)

    had = await images.exists(KIT_IMAGE)
    print(f"{KIT_IMAGE}: {'already held' if had else 'not held yet'}")
    try:
        await pull_and_inspect(images)
    finally:
        # Leave the daemon as it was, whatever happened.
        if not had and await images.exists(KIT_IMAGE):
            await images.remove(KIT_IMAGE)
            print(f"removed the {KIT_IMAGE} tag the example added")


async def list_images(images: Images) -> None:
    """Lists the images of the daemon, the largest first."""
    held = sorted(await images.list(), key=lambda image: image.size or 0, reverse=True)
    total = sum(image.size or 0 for image in held)
    print(f"{len(held)} images, {total // MIB} MiB in all")
    for image in held[:LISTED]:
        agent = f", agent {image.agent}" if image.agent else ""
        print(f"  {image.reference:<70} {(image.size or 0) // MIB:>6} MiB{agent}")


async def pull_and_inspect(images: Images) -> None:
    """Pulls the kit image twice, then reads its details and those of an unknown image.

    The first pull is followed as it happens, the second one waited for.

    Raises:
        ExampleError: When the pull fails, or an unknown image is not reported
            as such.
    """
    lines, last = 0, ""
    async with await images.pull_stream(KIT_IMAGE) as progress:
        async for line in progress:
            if line.error is not None:
                raise common.ExampleError(f"pull failed: {line.error}")
            lines += 1
            # Layers report the same status many times: print each change once.
            status = line.status or ""
            if status != last:
                print(f"  pull: {status}")
                last = status
    print(f"pulled {KIT_IMAGE}: {lines} progress lines")
    await images.pull(KIT_IMAGE)
    print("pulled again, waiting for the outcome: nothing to download")

    inspect = await images.inspect(KIT_IMAGE)
    metadata = await images.local_metadata(KIT_IMAGE)
    print(
        f"{KIT_IMAGE}: id {inspect.id}, agent {inspect.agent or 'none'}, "
        f"user {inspect.user or 'default'}, entrypoint {inspect.entrypoint}, "
        f"a local snapshot: {metadata.local_snapshot}"
    )

    if await images.exists(UNKNOWN):
        raise common.ExampleError(f"{UNKNOWN} exists")
    try:
        await images.export(UNKNOWN)
    except NotFoundError:
        pass
    else:
        raise common.ExampleError("an unknown image was exported")
    metadata = await images.local_metadata(UNKNOWN)
    print(
        f"{UNKNOWN}: does not exist, its export is not found, its local metadata "
        f"the defaults (a local snapshot: {metadata.local_snapshot})"
    )


if __name__ == "__main__":
    common.main(main)
