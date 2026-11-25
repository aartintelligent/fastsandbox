"""Fixtures: a fake daemon, a client connected to it, kit packages, and an
environment where code written for the real daemon runs against the fake one."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import fastsandbox
from fastsandbox import FastSandbox, Kit
from fastsandbox.models import ExecOutput
from fastsandbox.testing import FakeDaemon, fake_package

DOCS_SRC = Path(__file__).parent.parent / "docs_src"
"""The examples of the documentation, each tested by `tests/test_docs_src/`."""

CLAUDE_ARTIFACT = {
    "manifest": {"name": "claude", "binary": "claude", "runOptions": ["--yolo"]},
    "caps": {"network": {"allow": ["api.anthropic.com:443", "statsig.anthropic.com:443"]}},
}


@pytest.fixture
async def daemon() -> AsyncIterator[FakeDaemon]:
    async with FakeDaemon() as fake:
        yield fake


@pytest.fixture
async def client(daemon: FakeDaemon) -> fastsandbox.Client:
    return await fastsandbox.connect(daemon.socket_path)


@pytest.fixture
def package(tmp_path: Path) -> fastsandbox.KitPackage:
    return fake_package(tmp_path / "shell")


@pytest.fixture
def claude_package(tmp_path: Path) -> fastsandbox.KitPackage:
    return fake_package(tmp_path / "claude", agent="claude", artifact=CLAUDE_ARTIFACT)


@pytest.fixture
def make_app(daemon: FakeDaemon, package: fastsandbox.KitPackage) -> Callable[..., FastSandbox]:
    """Builds an application on the fake daemon, its tasks on the shell package."""

    def build(**options: Any) -> FastSandbox:
        return FastSandbox("ci", socket=str(daemon.socket_path), kit=package, **options)

    return build


@pytest.fixture
def fake_environment(
    daemon: FakeDaemon, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> FakeDaemon:
    """Points code written for the real daemon at the fake one.

    `DOCKER_SANDBOXES_API` names its socket, and the kit cache already holds
    packages of the `shell` and `claude` kits, compiled for its `sbx` version:
    `connect()`, `client.create(kit="shell")` and `FastSandbox()` need no
    change and no `sbx` CLI. Commands echo their last argument.
    """
    cache = tmp_path / "kits"
    fake_package(cache / Kit(base="shell").cache_key)
    fake_package(cache / Kit(base="claude").cache_key, agent="claude", artifact=CLAUDE_ARTIFACT)
    monkeypatch.setenv(fastsandbox.SOCKET_ENV, str(daemon.socket_path))
    monkeypatch.setenv("FASTSANDBOX_KIT_CACHE", str(cache))
    daemon.on_exec(lambda sandbox, cmd: ExecOutput(exit_code=0, stdout=f"{cmd[-1]}\n"))
    return daemon


@pytest.fixture
def load_example() -> Callable[[str], ModuleType]:
    """Loads an example of `docs_src/` by its relative path."""

    def load(relative: str) -> ModuleType:
        path = DOCS_SRC / relative
        name = "docs_src." + relative.removesuffix(".py").replace("/", ".")
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    return load
