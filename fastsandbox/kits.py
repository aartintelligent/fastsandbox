"""Kits: packages, their agent, the forge, the compiler, and a cache.

The daemon cannot resolve kit references by itself: a kit package holds what
the `sbx` CLI would send for a kit, and every sandbox of that kit is created
from it through the socket alone. `KitForge` writes it without the CLI, the
base kit rebuilt from its published image; `KitCompiler` captures it from the
CLI. `KitCache` forges packages on first use and keeps them in memory, or
compiles them with the CLI when given it. A composition (`Kit`) takes its
mixins as directories or written in Python (`fastsandbox.mixins`).
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
from .exceptions import KitForgeError
from .mixins import Mixin
from .models import Created, CreateRequest, PackageImage, SwapOutcome, wire

if TYPE_CHECKING:
    from .client import Client
    from .sandbox import Sandbox

__all__ = [
    "Kit",
    "KitAgent",
    "KitCache",
    "KitCompiler",
    "KitForge",
    "KitPackage",
    "default_cache_dir",
]

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
    """A kit package: forged without the `sbx` CLI, compiled by it, or opened from a directory.

    A package forged in memory has no directory, and its images are held in memory.
    """

    def __init__(self, native: _native.KitPackage) -> None:
        self._native = native

    @classmethod
    def open(cls, dir: str | os.PathLike[str]) -> KitPackage:
        """Opens the package forged or compiled into `dir`.

        Raises:
            KitPackageError: When `dir` holds no valid package.
        """
        return cls(_native.KitPackage.open(dir))

    @property
    def dir(self) -> Path | None:
        """The directory of the package, `None` for a package held in memory."""
        native = self._native.dir
        return Path(native) if native is not None else None

    @property
    def compiled_with(self) -> str | None:
        """The `sbx` version the package was compiled with, `None` for a forged package."""
        return self._native.compiled_with

    @property
    def compiled_api(self) -> str | None:
        """The daemon API version the package was forged or compiled for."""
        return self._native.compiled_api

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
        where = str(self.dir) if self.dir is not None else "memory"
        return f"KitPackage(dir={where!r}, kits={self.kit_refs!r})"


class KitForge:
    """Forges kits into packages without the `sbx` CLI, through the socket alone.

    The base kit is rebuilt from its published image, which the daemon pulls and exports;
    the mixins are read from their directories, whose `spec.yaml` is written in the JSON
    subset of YAML. Kit arguments are checked as the CLI checks them. A forged package is
    tied to the API of the daemon it was forged for.
    """

    def __init__(self, client: Client) -> None:
        """A forge for the daemon of `client`."""
        self._client = client

    async def forge(
        self, kit: Kit | str, output: str | os.PathLike[str] | None = None
    ) -> KitPackage:
        """Forges `kit`: in memory, or into the package directory `output` when given.

        Raises:
            KitForgeError: When the kit is one only the `sbx` CLI resolves (the directory of
                a local base kit, a mixin given by reference), or the kit policy of the
                daemon forbids forging it.
            InvalidKitError: When the forge refuses a descriptor or a kit argument.
            HostFileError: When a mixin directory or its `spec.yaml` cannot be read.
        """
        if isinstance(kit, str):
            kit = Kit(base=kit)
        forge = _native.KitForge(self._client.native)
        native = await forge.forge(
            published(kit.base),
            mixin_args(kit.mixins),
            dict(kit.args),
            os.fspath(output) if output is not None else None,
        )
        return KitPackage(native)


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
        mixins: tuple[str | Mixin, ...] | list[str | Mixin] = (),
        args: dict[str, str] | None = None,
    ) -> KitPackage:
        """Compiles a kit into the package directory `output`.

        `base` is `shell`, an agent, a reference or a kit directory, composed with `mixins` and
        kit `args`. A mixin written in Python is given to the CLI as a directory holding its
        `spec.yaml`, named after it and removed after the compilation: the CLI lists it under
        the path of that directory.

        Raises:
            KitCompileError: When the `sbx` CLI cannot compile the kit.

        """
        work = self._work_dir or Path(tempfile.mkdtemp(prefix="fastsandbox-kc-"))
        written = Path(tempfile.mkdtemp(prefix="fastsandbox-mixins-"))
        try:
            dirs = [
                os.fspath(write_mixin(mixin, written / str(index)))
                if isinstance(mixin, Mixin)
                else mixin
                for index, mixin in enumerate(mixins)
            ]
            compiler = _native.KitCompiler(self._sbx, self._client.native, work, self._timeout)
            native = await compiler.compile(base, output, dirs, dict(args or {}))
            return KitPackage(native)
        finally:
            shutil.rmtree(written, ignore_errors=True)
            if self._work_dir is None:
                shutil.rmtree(work, ignore_errors=True)


class Kit(BaseModel):
    """A kit to create sandboxes from: a base kit, mixins and kit arguments.

    Attributes:
        base: The base kit: an agent or `shell`, a kit reference, or the
            directory of a local kit.
        mixins: Mixin kits composed on top of the base, in order: directories,
            mixins written in Python (`Mixin`), or, for the CLI only, references.
        args: Kit arguments, as `sbx create --kit-arg` takes them.
    """

    model_config = ConfigDict(frozen=True)

    base: str = "shell"
    mixins: tuple[str | Mixin, ...] = ()
    args: dict[str, str] = {}

    @property
    def label(self) -> str:
        """A readable name of the composition, e.g. `shell+mixin@model=x`."""
        label = self.base
        for mixin in self.mixins:
            label += "+" + (mixin.name if isinstance(mixin, Mixin) else Path(mixin).name)
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
    """Kit packages, made on first use and kept for the next sandboxes.

    By default kits are forged without the `sbx` CLI (`KitForge`) and kept in memory for the
    process: nothing is written on the host, and a later process forges them again, in a few
    seconds once the daemon holds the image of the base kit. Given a directory, the cache keeps
    its packages there, for later processes too. Given the `sbx` CLI, it compiles kits with it
    (`KitCompiler`), which can take a few minutes for an agent kit, into its directory.

    A package is used again while it suits the daemon: one compiled by the CLI for the `sbx`
    version it runs, one forged for the API it speaks.
    """

    def __init__(
        self,
        directory: str | os.PathLike[str] | None = None,
        *,
        sbx: str | os.PathLike[str] | None = None,
        timeout: float | None = None,
    ) -> None:
        """A cache in memory, or in `directory`, compiling with the `sbx` program `sbx` if given.

        Args:
            directory: Where packages are kept; `$FASTSANDBOX_KIT_CACHE` when not given, else
                the memory of the process, or `default_cache_dir()` for a cache that
                compiles with the CLI.
            sbx: The `sbx` program to compile kits with, e.g. `"sbx"`; kits are forged
                without the CLI when not given.
            timeout: Deadline of a compilation by the CLI, in seconds.
        """
        if directory is None:
            directory = os.environ.get(CACHE_ENV) or None
        if directory is None and sbx is not None:
            directory = default_cache_dir()
        self.directory = Path(directory) if directory is not None else None
        self._sbx = sbx
        self._timeout = timeout
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}
        self._packages: dict[tuple[str, str], KitPackage] = {}

    @classmethod
    def default(cls) -> KitCache:
        """The kit cache of the process, shared by the clients given none.

        One per value of `$FASTSANDBOX_KIT_CACHE`, so that a change of it takes effect.
        """
        return _SHARED.setdefault(os.environ.get(CACHE_ENV) or None, cls())

    async def package(self, client: Client, kit: Kit | str) -> KitPackage:
        """The package of `kit` for the daemon of `client`, made now unless already kept.

        Raises:
            KitForgeError: When the kit is one only the `sbx` CLI resolves, for a cache
                that forges.
            InvalidKitError: When the forge refuses a descriptor or a kit argument.
            KitCompileError: When the `sbx` CLI cannot compile the kit, for a cache that
                compiles.
        """
        if isinstance(kit, str):
            kit = Kit(base=kit)
        key = (str(client.socket_path), kit.cache_key)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            held = self._packages.get(key)
            if held is not None and suits(held, client):
                return held
            output = self.directory / kit.cache_key if self.directory is not None else None
            if output is not None:
                try:
                    package: KitPackage | None = KitPackage.open(output)
                except Exception:
                    package = None
                if package is not None and suits(package, client):
                    self._packages[key] = package
                    return package
                output.parent.mkdir(parents=True, exist_ok=True)
            if self._sbx is not None and output is not None:
                compiler = KitCompiler(client, sbx=self._sbx, timeout=self._timeout)
                made = await compiler.compile(kit.base, output, mixins=kit.mixins, args=kit.args)
            else:
                made = await KitForge(client).forge(kit, output)
            self._packages[key] = made
            return made

    def __repr__(self) -> str:
        where = str(self.directory) if self.directory is not None else "memory"
        how = f"sbx={os.fspath(self._sbx)!r}" if self._sbx is not None else "forged"
        return f"KitCache({where!r}, {how})"


_SHARED: dict[str | None, KitCache] = {}
"""The caches `KitCache.default` gives, by value of `$FASTSANDBOX_KIT_CACHE`."""


def suits(package: KitPackage, client: Client) -> bool:
    """Whether `package` suits the daemon of `client`.

    A package compiled by the CLI suits the `sbx` version it was compiled with, a forged one
    the API it was forged for.
    """
    if package.compiled_with is not None:
        return package.compiled_with == client.health.version
    return package.compiled_api == client.health.api_version


def published(base: str) -> str:
    """The reference of the published base kit `base`, as the CLI names it.

    A bare name is a kit of `docker.io/sbx`, e.g. `shell` or `claude`.

    Raises:
        KitForgeError: When `base` is the directory of a local kit.
    """
    if base.startswith((".", "/", "~")) or Path(base).expanduser().is_dir():
        raise KitForgeError(
            f"the base kit {base} is the directory of a local kit, which only the sbx CLI "
            'resolves: give the kit cache the CLI, KitCache(sbx="sbx")'
        )
    if "/" in base or ":" in base or "@" in base:
        return base
    return f"docker.io/sbx/{base}:latest"


def mixin_args(mixins: tuple[str | Mixin, ...]) -> list[str | tuple[str, str]]:
    """`mixins`, as the native forge takes them.

    Directories, and the reference and the descriptor in JSON of those written in Python.

    Raises:
        KitForgeError: When a mixin is not a directory, but a reference.
    """
    forged: list[str | tuple[str, str]] = []
    for mixin in mixins:
        if isinstance(mixin, Mixin):
            forged.append((mixin.reference, mixin.descriptor.model_dump_json()))
            continue
        path = Path(mixin).expanduser()
        if not path.is_dir():
            raise KitForgeError(
                f"the mixin {mixin} is not a directory: a mixin given by reference only the "
                'sbx CLI resolves, give the kit cache the CLI, KitCache(sbx="sbx")'
            )
        forged.append(os.fspath(path))
    return forged


def write_mixin(mixin: Mixin, parent: Path) -> Path:
    """Writes the `spec.yaml` of `mixin` into a directory of `parent` named after it."""
    directory = parent / mixin.name
    directory.mkdir(parents=True)
    (directory / "spec.yaml").write_text(mixin.descriptor.to_spec())
    return directory
