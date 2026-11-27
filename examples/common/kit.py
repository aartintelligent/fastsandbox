"""Kit packages for the examples: forged without the `sbx` CLI, or compiled by it when asked.

The daemon cannot resolve kit references by itself: a package holds what the
CLI would send for a kit, and every sandbox of that kit is created from it
through the socket alone. The examples take their packages from the kit cache
of the library (`fastsandbox.KitCache`): forged without the CLI and kept in
memory for the run, the base kit rebuilt from its published image, which the
daemon pulls once. A composition only the CLI resolves, such as a mixin whose
`spec.yaml` is written in YAML, is compiled by it when asked (`sbx=True`),
into `~/.cache/fastsandbox/kits` unless `FASTSANDBOX_KIT_CACHE` names another
directory: that runs `sbx create` once on a throw-away sandbox and can take a
few minutes for an agent kit, and the package is compiled again when the
daemon runs another `sbx` version. This module only adds a message before a
kit is made.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from fastsandbox import Kit, KitCache, KitPackage
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
    sbx: bool = False,
) -> KitPackage:
    """The package of the kit `base` (`shell`, `claude`, `opencode`, …), made on first use.

    Args:
        client: The client of the daemon the package is for.
        base: The base kit: `shell`, an agent or a published reference; a kit
            directory needs `sbx`.
        mixins: Directories of mixin kits composed on top of the base, in
            order; a composition is kept apart from its base kit.
        args: Kit arguments (`name=value` for every kit, `kit.name=value` for
            one), as `sbx create --kit-arg` takes them.
        sbx: Compiles the kit with the `sbx` CLI instead of forging it.

    Raises:
        KitForgeError: When only the `sbx` CLI resolves the kit, and `sbx` is not set.
        InvalidKitError: When the forge refuses a mixin, an argument the kit
            does not declare or a value its pattern refuses.
        KitCompileError: When the `sbx` CLI cannot compile the kit.
    """
    kit = _kit(base, mixins, args)
    if not sbx:
        print(f"forging the {kit.label} kit without the sbx CLI", file=sys.stderr)
        return await client.package(kit)
    cache = KitCache(sbx="sbx")
    try:
        directory = cache.directory or Path()
        cached = KitPackage.open(directory / kit.cache_key)
        fresh = cached.compiled_with == client.health.version
    except KitPackageError:
        fresh = False
    if not fresh:
        print(
            f"compiling the {kit.label} kit with the sbx CLI (first run only, it can take a while)",
            file=sys.stderr,
        )
    return await cache.package(client, kit)


def _kit(
    base: str, mixins: Sequence[str | os.PathLike[str]], args: Mapping[str, str] | None
) -> Kit:
    """The composition of `base`, `mixins` and `args`, mixins by absolute path."""
    return Kit(
        base=base,
        mixins=tuple(os.fspath(Path(mixin).resolve()) for mixin in mixins),
        args=dict(args or {}),
    )
