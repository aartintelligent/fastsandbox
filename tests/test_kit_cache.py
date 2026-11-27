"""The kit cache: kits forged in memory, kept in a directory, or compiled by the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import fastsandbox
from fastsandbox import Kit, KitCache
from fastsandbox.kits import default_cache_dir, suits
from fastsandbox.testing import FakeDaemon, fake_package


async def test_kits_are_forged_once_and_kept_in_memory(
    client: fastsandbox.Client, daemon: FakeDaemon
) -> None:
    cache = KitCache()
    assert cache.directory is None
    first = await cache.package(client, "shell")
    assert first.dir is None
    assert await cache.package(client, Kit(base="shell")) is first
    assert len(daemon.requests_to("POST", "/docker/images/create")) == 1
    assert "memory" in repr(cache)


async def test_a_directory_keeps_the_packages_for_later_caches(
    client: fastsandbox.Client, daemon: FakeDaemon, tmp_path: Path
) -> None:
    forged = await KitCache(tmp_path).package(client, "shell")
    assert forged.dir == tmp_path / Kit(base="shell").cache_key
    again = await KitCache(tmp_path).package(client, "shell")
    assert again.kit_refs == forged.kit_refs
    assert len(daemon.requests_to("POST", "/docker/images/create")) == 1


async def test_a_package_written_by_fake_package_is_used_as_it_is(
    client: fastsandbox.Client, daemon: FakeDaemon, tmp_path: Path
) -> None:
    written = fake_package(tmp_path / Kit(base="shell").cache_key)
    assert suits(written, client)
    package = await KitCache(tmp_path).package(client, "shell")
    assert package.dir == written.dir
    assert daemon.requests_to("POST", "/docker/images/create") == []


async def test_a_package_for_another_sbx_version_is_made_again(
    client: fastsandbox.Client, tmp_path: Path
) -> None:
    stale = fake_package(tmp_path / Kit(base="shell").cache_key, sbx_version="v0.1.0")
    assert not suits(stale, client)
    package = await KitCache(tmp_path).package(client, "shell")
    assert package.compiled_with is None


def test_the_environment_names_the_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FASTSANDBOX_KIT_CACHE", str(tmp_path))
    assert KitCache().directory == tmp_path
    assert KitCache.default() is KitCache.default()
    assert KitCache.default().directory == tmp_path
    monkeypatch.delenv("FASTSANDBOX_KIT_CACHE")
    assert KitCache.default().directory is None


def test_a_cache_that_compiles_with_the_cli_keeps_its_packages_on_disk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FASTSANDBOX_KIT_CACHE", raising=False)
    cache = KitCache(sbx="sbx")
    assert cache.directory == default_cache_dir()
    assert "sbx='sbx'" in repr(cache)


async def test_a_cache_given_the_cli_compiles_into_its_directory(
    client: fastsandbox.Client, compiled: list[dict[str, Any]], tmp_path: Path
) -> None:
    kit = Kit(base="shell", mixins=("./kits/tools",), args={"model": "fast"})
    cache = KitCache(tmp_path, sbx="/opt/sbx", timeout=60)
    package = await cache.package(client, kit)
    assert package.dir == tmp_path / kit.cache_key
    assert await cache.package(client, kit) is package
    assert compiled == [
        {
            "sbx": "/opt/sbx",
            "timeout": 60,
            "base": "shell",
            "output": tmp_path / kit.cache_key,
            "mixins": ("./kits/tools",),
            "args": {"model": "fast"},
        }
    ]


async def test_clients_share_the_cache_of_the_process(client: fastsandbox.Client) -> None:
    other = fastsandbox.Client(client.native)
    assert client.kits is other.kits is KitCache.default()
