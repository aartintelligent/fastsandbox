"""Kit packages compiled once with the `sbx` CLI, then replayed through the socket alone.

The daemon cannot resolve kit references by itself: a package captures what
the CLI sends once, and every later sandbox of that kit is created from it.
The examples use the kit cache of the library (`fastsandbox.KitCache`, under
`~/.cache/fastsandbox/kits` unless `FASTSANDBOX_KIT_CACHE` names another
directory), which compiles a kit again when the daemon runs another `sbx`
version. This module only adds a message before a compilation, which runs
`sbx create` once on a throw-away sandbox and can take a few minutes for an
agent kit; the kit images it pulls stay on the daemon as the cache of the next
sandboxes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from fastsandbox import Kit, KitPackage
from fastsandbox.exceptions import KitPackageError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from fastsandbox import Client

__all__ = ["package"]


async def package(
    client: Client,
    base: str = "shell",
    *,
    mixins: Sequence[str | os.PathLike[str]] = (),
    args: Mapping[str, str] | None = None,
) -> KitPackage:
    """The package of the kit `base` (`shell`, `claude`, `opencode`, …), compiled on first use.

    Args:
        client: The client of the daemon the package is for.
        base: The base kit: `shell`, an agent, a reference or a kit directory.
        mixins: Directories of mixin kits composed on top of the base, in
            order; a composition is cached apart from its base kit.
        args: Kit arguments (`name=value` for every kit, `kit.name=value` for
            one), as `sbx create --kit-arg` takes them.

    Raises:
        KitCompileError: When the `sbx` CLI cannot compile the kit, an argument
            the kit does not declare or a value its pattern refuses included.
    """
    kit = _kit(base, mixins, args)
    try:
        cached = KitPackage.open(client.kits.directory / kit.cache_key)
        fresh = cached.compiled_with == client.health.version
    except KitPackageError:
        fresh = False
    if not fresh:
        print(
            f"compiling the {kit.label} kit with the sbx CLI (first run only, it can take a while)",
            file=sys.stderr,
        )
    return await client.package(kit)


def _kit(
    base: str, mixins: Sequence[str | os.PathLike[str]], args: Mapping[str, str] | None
) -> Kit:
    """The composition of `base`, `mixins` and `args`, mixins by absolute path."""
    return Kit(
        base=base,
        mixins=tuple(os.fspath(Path(mixin).resolve()) for mixin in mixins),
        args=dict(args or {}),
    )
