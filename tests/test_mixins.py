"""Mixins written in Python: built as the crate builds them, checked by it, forged and compiled."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest

import fastsandbox
from fastsandbox import Kit, KitCompiler, KitDescriptor, KitForge, LifecycleStep, Mixin, _native
from fastsandbox.exceptions import HostFileError, InvalidKitError
from fastsandbox.mixins import GATEWAY_ENV, LifecycleCapability, NetworkCapability
from fastsandbox.testing import fake_package

ACME = (
    KitDescriptor.mixin("Acme")
    .with_version("1.0.0")
    .with_description("Acme tools")
    .with_network_allow("a.example.com:443")
    .with_network_deny("b.example.com")
    .with_install(LifecycleStep(command="echo hi").with_env("MCP_GATEWAY_URL"))
    .with_startup(LifecycleStep(command="date").in_background())
)
"""A descriptor with a capability of each kind, the one the crate tests build."""


def test_a_descriptor_is_built_as_the_crate_builds_it() -> None:
    assert ACME.to_json() == {
        "schemaVersion": "3",
        "kind": "mixin",
        "displayName": "Acme",
        "description": "Acme tools",
        "version": "1.0.0",
        "capabilities": [
            {
                "type": "com.docker.sandbox/network-policy@1",
                "config": {"runtime": {"allow": ["a.example.com:443"], "deny": ["b.example.com"]}},
            },
            {
                "type": "com.docker.sandbox/lifecycle@1",
                "config": {
                    "install": [{"command": "echo hi", "env": ["MCP_GATEWAY_URL"]}],
                    "startup": [{"command": "date", "background": True}],
                },
            },
        ],
    }
    assert json.loads(ACME.model_dump_json()) == ACME.to_json()
    # A capability of a kind the descriptor holds already is added to, not repeated.
    more = ACME.with_network_allow("c.example.com").with_install(LifecycleStep(command="true"))
    network, lifecycle = more.capabilities
    assert isinstance(network, NetworkCapability)
    assert network.config.runtime.allow == ("a.example.com:443", "c.example.com")
    assert isinstance(lifecycle, LifecycleCapability)
    assert [step.command for step in lifecycle.config.install] == ["echo hi", "true"]


def test_steps_take_the_options_of_the_crate() -> None:
    step = (
        LifecycleStep(command=["pip", "install", "acme-cli"])
        .as_user("agent")
        .with_description("Installs the Acme CLI")
        .with_gateway_env()
        .with_env("ACME_HOME")
    )
    assert step.model_dump(mode="json") == {
        "command": ["pip", "install", "acme-cli"],
        "user": "agent",
        "description": "Installs the Acme CLI",
        "env": [*GATEWAY_ENV, "ACME_HOME"],
    }


def test_the_spec_yaml_reads_back_as_it_was_written(tmp_path: Path) -> None:
    spec = ACME.to_spec()
    assert spec.startswith("# syntax=docker/sandbox-kit:3\n{\n")
    assert KitDescriptor.parse(spec) == ACME
    assert KitDescriptor.from_json(ACME.to_json()) == ACME
    directory = tmp_path / "acme-tools"
    directory.mkdir()
    (directory / "spec.yaml").write_text(spec)
    assert KitDescriptor.read(directory / "spec.yaml") == ACME
    mixin = Mixin.read(directory)
    assert mixin.reference == os.fspath(directory.resolve())
    assert mixin.name == "acme-tools"
    assert mixin.descriptor == ACME


def test_fields_keep_the_names_of_the_format() -> None:
    by_alias = KitDescriptor.model_validate(
        {"displayName": "A", "sourceUrl": "https://example.com/a", "author": {"name": "A"}}
    )
    by_name = KitDescriptor(
        display_name="A", source_url="https://example.com/a", author={"name": "A"}
    )
    assert by_alias == by_name
    assert by_name.to_json() == {
        "schemaVersion": "3",
        "kind": "mixin",
        "displayName": "A",
        "author": {"name": "A"},
        "sourceUrl": "https://example.com/a",
        "capabilities": [],
    }


@pytest.mark.parametrize(
    ("descriptor", "reason"),
    [
        (ACME.with_network_allow("https://api.example.com"), "a host, not a URL"),
        (KitDescriptor.mixin("E").with_install(LifecycleStep(command=" ")), "no command"),
        (
            KitDescriptor.mixin("B").with_install(LifecycleStep(command="x").in_background()),
            "only startup commands run in the background",
        ),
        (
            KitDescriptor.mixin("V").with_install(LifecycleStep(command="x").with_env("1BAD")),
            "1BAD is not a variable name",
        ),
        (KitDescriptor(display_name="U", unknown=1), "unknown field `unknown`"),
        (
            KitDescriptor.mixin("K").with_install(LifecycleStep(command="echo ${{ model }}")),
            "kit arguments are not supported",
        ),
    ],
    ids=["url", "empty", "background", "variable", "field", "argument"],
)
def test_a_mixin_the_forge_would_refuse_is_refused_when_made(
    descriptor: KitDescriptor, reason: str
) -> None:
    with pytest.raises(InvalidKitError) as refused:
        Mixin(reference="/kits/refused", descriptor=descriptor)
    assert reason in refused.value.reason


def test_a_mixin_needs_a_reference_that_names_it() -> None:
    with pytest.raises(InvalidKitError, match="names it"):
        Mixin(reference="/", descriptor=ACME)
    assert Mixin(reference="/kits/acme/", descriptor=ACME).name == "acme"


def test_a_descriptor_not_in_json_is_refused(tmp_path: Path) -> None:
    with pytest.raises(InvalidKitError, match="JSON subset of YAML"):
        KitDescriptor.parse('schemaVersion: "3"\nkind: mixin\n')
    with pytest.raises(HostFileError):
        Mixin.read(tmp_path / "missing")


async def test_written_mixins_are_forged_in_order_with_those_of_directories(
    client: fastsandbox.Client, tmp_path: Path
) -> None:
    directory = tmp_path / "other"
    directory.mkdir()
    (directory / "spec.yaml").write_text(KitDescriptor.mixin("Other").to_spec())
    acme = Mixin(reference="/kits/acme-tools", descriptor=ACME)
    kit = Kit(base="shell", mixins=(acme, str(directory)))
    assert kit.label == "shell+acme-tools+other"
    package = await KitForge(client).forge(kit)
    assert package.kit_refs[1:] == ["/kits/acme-tools", os.fspath(directory.resolve())]


def test_each_written_mixin_is_kept_apart() -> None:
    first = Mixin(reference="/kits/acme-tools", descriptor=ACME)
    second = Mixin(reference="/kits/acme-tools", descriptor=ACME.with_version("2.0.0"))
    keys = {Kit(mixins=(mixin,)).cache_key for mixin in (first, second)}
    assert len(keys) == 2
    assert Kit(mixins=(first,)).cache_key == Kit(mixins=(first,)).cache_key


async def test_the_cli_is_given_written_mixins_as_directories(
    client: fastsandbox.Client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    given: list[tuple[str, str]] = []

    class Compiler:
        def __init__(self, sbx: str, native: Any, work: Path, timeout: float | None) -> None:
            pass

        async def compile(
            self, base: str, output: Path, mixins: list[str], args: dict[str, str]
        ) -> _native.KitPackage:
            for mixin in mixins:
                spec = Path(mixin) / "spec.yaml"
                given.append((mixin, spec.read_text() if spec.is_file() else ""))
            fake_package(output)
            return _native.KitPackage.open(output)

    monkeypatch.setattr(_native, "KitCompiler", Compiler)
    acme = Mixin(reference="/kits/acme-tools", descriptor=ACME)
    await KitCompiler(client).compile("shell", tmp_path / "out", mixins=[acme, "./kits/other"])
    (written, spec), (other, _) = given
    assert Path(written).name == "acme-tools"
    assert KitDescriptor.parse(spec) == ACME
    assert other == "./kits/other"
    # The directory written for the CLI goes with the compilation.
    assert not await asyncio.to_thread(Path(written).exists)
