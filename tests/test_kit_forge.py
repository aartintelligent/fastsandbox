"""Kits forged without the `sbx` CLI, against the published kits of the fake daemon."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import fastsandbox
from fastsandbox import Kit, KitForge, KitPackage
from fastsandbox.exceptions import (
    HostFileError,
    InvalidKitError,
    KitForgeError,
    OperationFailedError,
)
from fastsandbox.testing import FakeDaemon

MIXIN = {
    "schemaVersion": "3",
    "kind": "mixin",
    "displayName": "Tools",
    "capabilities": [
        {
            "type": "com.docker.sandbox/lifecycle@1",
            "config": {"install": [{"command": "echo installed > /tmp/tools", "user": "agent"}]},
        }
    ],
}


def mixin(directory: Path, spec: str | None = None) -> Path:
    """A mixin directory whose `spec.yaml` is `spec`, the tools mixin in JSON by default."""
    directory.mkdir(parents=True)
    (directory / "spec.yaml").write_text(spec if spec is not None else json.dumps(MIXIN))
    return directory


async def test_the_shell_kit_is_forged_in_memory(client: fastsandbox.Client) -> None:
    package = await KitForge(client).forge("shell")
    assert package.dir is None
    assert package.compiled_with is None
    assert package.compiled_api == client.health.api_version
    assert package.kit_refs[0].startswith("docker.io/sbx/shell@sha256:")
    assert package.images == []
    assert package.agent is not None
    assert package.agent.binary == "bash"
    assert "memory" in repr(package)


async def test_an_agent_kit_carries_its_agent_and_its_hosts(
    client: fastsandbox.Client, daemon: FakeDaemon
) -> None:
    package = await KitForge(client).forge(Kit(base="claude"))
    assert package.agent is not None
    assert package.agent.binary == "claude"
    assert package.agent.hosts() == ["api.anthropic.com"]
    # The capability the kit declares and the CLI does not support is left out, as by the CLI.
    artifact = package.kit_artifacts[0]
    effective = [capability["type"] for capability in artifact["v3Effective"]["capabilities"]]
    assert "com.docker.sandbox/open-url@1" not in effective
    assert artifact["v3Selection"]["skipped"][-1]["decisions"][0]["message"] == (
        "unsupported capability type com.docker.sandbox/open-url@1"
    )
    sandbox = await client.create("job-1", kit=package)
    assert sandbox.name == "job-1"
    assert daemon.sandboxes["job-1"]["request"]["kits"] == package.kit_refs


async def test_a_kit_is_forged_into_a_directory_when_given_one(
    client: fastsandbox.Client, tmp_path: Path
) -> None:
    output = tmp_path / "shell"
    package = await KitForge(client).forge("docker.io/sbx/shell:latest", output)
    assert package.dir == output
    assert KitPackage.open(output).kit_refs == package.kit_refs


async def test_the_images_of_a_package_on_disk_are_files_of_its_directory(
    client: fastsandbox.Client, tmp_path: Path
) -> None:
    tools = mixin(tmp_path / "tools")
    output = tmp_path / "package"
    package = await KitForge(client).forge(Kit(base="shell", mixins=(str(tools),)), output)
    for held in (package, KitPackage.open(output)):
        paths = [image.path for image in held.images]
        assert len(paths) == 1
        assert isinstance(paths[0], str)
        assert Path(paths[0]).is_relative_to(output)


async def test_mixins_are_read_from_their_directories(
    client: fastsandbox.Client, tmp_path: Path
) -> None:
    tools = mixin(tmp_path / "tools")
    package = await KitForge(client).forge(Kit(base="shell", mixins=(str(tools),)))
    assert len(package.kit_refs) == 2
    assert [image.path for image in package.images] == [None]
    assert package.images[0].reference is not None


async def test_a_mixin_in_yaml_is_refused_before_anything_is_sent(
    client: fastsandbox.Client, daemon: FakeDaemon, tmp_path: Path
) -> None:
    yaml = mixin(tmp_path / "yaml", 'schemaVersion: "3"\nkind: mixin\ndisplayName: YAML\n')
    with pytest.raises(InvalidKitError) as refused:
        await KitForge(client).forge(Kit(base="shell", mixins=(str(yaml),)))
    assert refused.value.kit is not None
    assert refused.value.reason
    assert daemon.requests_to("POST", "/docker/images/create") == []


async def test_an_argument_the_kit_does_not_declare_is_refused(client: fastsandbox.Client) -> None:
    with pytest.raises(InvalidKitError) as refused:
        await KitForge(client).forge(Kit(base="shell", args={"model": "fast"}))
    assert "model" in refused.value.message


async def test_kits_only_the_cli_resolves_say_so(
    client: fastsandbox.Client, tmp_path: Path
) -> None:
    local = tmp_path / "local-kit"
    local.mkdir()
    with pytest.raises(KitForgeError, match='KitCache\\(sbx="sbx"\\)'):
        await KitForge(client).forge(str(local))
    with pytest.raises(KitForgeError, match="not a directory"):
        await KitForge(client).forge(Kit(base="shell", mixins=("docker.io/acme/mixin:1",)))


async def test_a_bare_name_is_the_published_kit_whatever_the_working_directory_holds(
    client: fastsandbox.Client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "shell").mkdir()
    monkeypatch.chdir(tmp_path)
    package = await KitForge(client).forge("shell")
    assert package.kit_refs[0].startswith("docker.io/sbx/shell@sha256:")


async def test_a_path_to_no_directory_says_so(client: fastsandbox.Client, tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(HostFileError) as base:
        await KitForge(client).forge(str(missing))
    assert base.value.path == str(missing)
    with pytest.raises(HostFileError):
        await KitForge(client).forge(Kit(base="shell", mixins=("./missing-mixin",)))


async def test_the_kit_policy_of_the_daemon_is_followed(
    client: fastsandbox.Client, daemon: FakeDaemon, tmp_path: Path
) -> None:
    daemon.settings["kit.allowLocalKits"] = False
    with pytest.raises(KitForgeError, match="local kits"):
        await KitForge(client).forge(Kit(base="shell", mixins=(str(mixin(tmp_path / "t")),)))
    daemon.settings["kit.requireSignature"] = True
    with pytest.raises(KitForgeError, match="signed kits"):
        await KitForge(client).forge("shell")


async def test_a_kit_the_daemon_cannot_pull_fails(client: fastsandbox.Client) -> None:
    with pytest.raises(OperationFailedError, match="pull access denied"):
        await KitForge(client).forge("codex")
