"""Kits: compiled packages, their agent, the compiler, and a cache.

The daemon cannot resolve kit references by itself: a kit package captures
what the `sbx` CLI sends for a kit, once, and every later sandbox of that kit is
created from it through the socket alone. `KitCache` compiles packages on first
use and compiles them again when the daemon runs another `sbx` version.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from . import _native
from .models import Created, CreateRequest, PackageImage, SwapOutcome, wire

if TYPE_CHECKING:
    from .client import Client
    from .sandbox import Sandbox

__all__ = ["Kit", "KitAgent", "KitCache", "KitCompiler", "KitPackage", "default_cache_dir"]

CACHE_ENV = "FASTSANDBOX_KIT_CACHE"
"""Environment variable overriding the directory of the kit cache."""


def default_cache_dir() -> Path:
    """The default directory of the kit cache.

    `$FASTSANDBOX_KIT_CACHE`, else `$XDG_CACHE_HOME/fastsandbox/kits`, else
    `~/.cache/fastsandbox/kits`.
    """
    if override := os.environ.get(CACHE_ENV):
        return Path(override)
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "fastsandbox" / "kits"


class KitAgent:
    """The agent a kit describes: its program, run options and network needs."""

    def __init__(self, native: _native.KitAgent) -> None:
        self._native = native

    @classmethod
    def from_artifact(cls, artifact: Any) -> KitAgent | None:
        """The agent described by a kit artifact, if it describes one."""
        native = _native.KitAgent.from_artifact(artifact)
        return cls(native) if native is not None else None

    @property
    def name(self) -> str:
        """The name of the agent, e.g. `claude`."""
        return self._native.name

    @property
    def display_name(self) -> str | None:
        """The display name of the agent."""
        return self._native.display_name

    @property
    def binary(self) -> str | None:
        """The program of the agent."""
        return self._native.binary

    @property
    def run_options(self) -> list[str]:
        """The options the kit runs the agent with."""
        return self._native.run_options

    @property
    def network(self) -> list[str]:
        """The network entries the kit declares."""
        return self._native.network

    def command(self, *args: str) -> list[str]:
        """The command line that runs the agent with `args`."""
        return self._native.command(list(args))

    def hosts(self) -> list[str]:
        """The hosts the agent needs to reach."""
        return self._native.hosts()

    def __repr__(self) -> str:
        return f"KitAgent(name={self.name!r})"


class KitPackage:
    """A compiled kit package."""

    def __init__(self, native: _native.KitPackage) -> None:
        self._native = native

    @classmethod
    def open(cls, dir: str | os.PathLike[str]) -> KitPackage:
        """Opens the package compiled into `dir`.

        Raises:
            KitPackageError: When `dir` holds no valid package.
        """
        return cls(_native.KitPackage.open(dir))

    @property
    def dir(self) -> Path:
        """The directory of the package."""
        return Path(self._native.dir)

    @property
    def compiled_with(self) -> str | None:
        """The `sbx` version the package was compiled with."""
        return self._native.compiled_with

    @property
    def kit_refs(self) -> list[str]:
        """The kit references of the package, base kit first."""
        return self._native.kit_refs

    @property
    def agent(self) -> KitAgent | None:
        """The agent the base kit describes, if any."""
        native = self._native.agent
        return KitAgent(native) if native is not None else None

    @property
    def kit_artifacts(self) -> list[Any]:
        """The kit artifacts, as the daemon receives them."""
        return self._native.kit_artifacts

    @property
    def images(self) -> list[PackageImage]:
        """The image archives of the package."""
        return [PackageImage.model_validate(image) for image in self._native.images]

    def request(self, name: str) -> CreateRequest:
        """The creation request of a sandbox named `name` from this package."""
        return CreateRequest.model_validate(self._native.request(name))

    async def load_images(self, client: Client) -> int:
        """Loads the images of the package into the daemon; returns how many."""
        return await self._native.load_images(client.native)

    async def create(self, client: Client, name: str) -> Created:
        """Loads the images and creates the sandbox `name` from the package."""
        return Created.model_validate(await self._native.create(client.native, name))

    async def create_with(self, client: Client, request: CreateRequest) -> Created:
        """Loads the images and creates a sandbox from an adjusted request.

        The request comes from `request`, adjusted by the caller.
        """
        return Created.model_validate(await self._native.create_with(client.native, wire(request)))

    async def install_into(self, sandbox: Sandbox) -> int:
        """Installs the kits in place in a running sandbox.

        Returns how many artifacts were installed.
        """
        return await self._native.install_into(sandbox.native)

    async def add_to(self, sandbox: Sandbox) -> SwapOutcome:
        """Adds the kits to a sandbox by swapping its container."""
        return SwapOutcome.model_validate(await self._native.add_to(sandbox.native))

    def __repr__(self) -> str:
        return f"KitPackage(dir={str(self.dir)!r}, kits={self.kit_refs!r})"


class KitCompiler:
    """Compiles kits into packages with the `sbx` CLI.

    It runs the CLI once behind a capturing proxy, on a throw-away sandbox.
    """

    def __init__(
        self,
        client: Client,
        *,
        sbx: str | os.PathLike[str] = "sbx",
        work_dir: str | os.PathLike[str] | None = None,
        timeout: float | None = None,
    ) -> None:
        """A compiler for the daemon of `client`.

        Args:
            client: The client of the daemon.
            sbx: The `sbx` program, found on `PATH` by default.
            work_dir: Scratch directory of the compiler; a temporary one,
                removed after each compilation, by default.
            timeout: Deadline of a compilation, in seconds.
        """
        self._client = client
        self._sbx = os.fspath(sbx)
        self._work_dir = Path(work_dir) if work_dir is not None else None
        self._timeout = timeout

    async def compile(
        self,
        base: str,
        output: str | os.PathLike[str],
        *,
        mixins: tuple[str, ...] | list[str] = (),
        args: dict[str, str] | None = None,
    ) -> KitPackage:
        """Compiles a kit into the package directory `output`.

        `base` is `shell`, an agent, a reference or a kit directory, composed with `mixins` and
        kit `args`.

        Raises:
            KitCompileError: When the `sbx` CLI cannot compile the kit.

        """
        work = self._work_dir or Path(tempfile.mkdtemp(prefix="fastsandbox-kc-"))
        try:
            compiler = _native.KitCompiler(self._sbx, self._client.native, work, self._timeout)
            native = await compiler.compile(base, output, list(mixins), dict(args or {}))
            return KitPackage(native)
        finally:
            if self._work_dir is None:
                shutil.rmtree(work, ignore_errors=True)


class Kit(BaseModel):
    """A kit to create sandboxes from: a base kit, mixins and kit arguments.

    Attributes:
        base: The base kit: an agent or `shell`, a kit reference, or the
            directory of a local kit.
        mixins: Mixin kits composed on top of the base, in order.
        args: Kit arguments, as `sbx create --kit-arg` takes them.
    """

    model_config = ConfigDict(frozen=True)

    base: str = "shell"
    mixins: tuple[str, ...] = ()
    args: dict[str, str] = {}

    @property
    def label(self) -> str:
        """A readable name of the composition, e.g. `shell+mixin@model=x`."""
        label = self.base
        for mixin in self.mixins:
            label += "+" + Path(mixin).name
        if self.args:
            label += "@" + ",".join(f"{k}={v}" for k, v in sorted(self.args.items()))
        return label

    @property
    def cache_key(self) -> str:
        """The directory name of the composition in a kit cache."""
        digest = hashlib.sha256(
            json.dumps(self.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()[:12]
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(self.base).name).strip("-") or "kit"
        return f"{slug}-{digest}"


class KitCache:
    """Kit packages compiled on first use.

    They are cached by composition, and compiled again when the daemon runs another `sbx`
    version.

    The first compilation of a kit runs `sbx create` once on a throw-away
    sandbox, which can take a few minutes for an agent kit; the kit images it
    pulls stay on the daemon for the next sandboxes.

    """

    def __init__(
        self,
        directory: str | os.PathLike[str] | None = None,
        *,
        sbx: str | os.PathLike[str] = "sbx",
        timeout: float | None = None,
    ) -> None:
        """A cache in `directory`, compiling with the `sbx` program `sbx`.

        The directory is `default_cache_dir()` by default.
        """
        self.directory = Path(directory) if directory is not None else default_cache_dir()
        self._sbx = sbx
        self._timeout = timeout
        self._locks: dict[str, asyncio.Lock] = {}

    async def package(self, client: Client, kit: Kit | str) -> KitPackage:
        """The package of `kit`, compiled now unless already cached.

        A cached package is used when it was compiled for the `sbx` version of the daemon.
        """
        if isinstance(kit, str):
            kit = Kit(base=kit)
        output = self.directory / kit.cache_key
        lock = self._locks.setdefault(kit.cache_key, asyncio.Lock())
        async with lock:
            try:
                package = KitPackage.open(output)
            except Exception:
                package = None
            if package is not None and package.compiled_with == client.health.version:
                return package
            output.parent.mkdir(parents=True, exist_ok=True)
            compiler = KitCompiler(client, sbx=self._sbx, timeout=self._timeout)
            return await compiler.compile(kit.base, output, mixins=kit.mixins, args=kit.args)
