"""A shell sandbox from a package forged without the `sbx` CLI, with mixins written in Python.

`KitForge` makes the package itself, without the `sbx` CLI, not even once:

- the **base kit** is `docker.io/sbx/shell:latest`, rebuilt from its
  published image: the daemon pulls and exports it, and the descriptor of the
  kit is read from the image;
- a **mixin written in Python** (`KitDescriptor`, `LifecycleStep`): an
  install command given the variables of the MCP gateway of the sandbox, a
  startup command run in the background, a host allowed and one denied while
  the sandbox runs;
- a **mixin read from its directory**,
  [`json-mixin`](kits/json-mixin/spec.yaml), a `spec.yaml` written in the
  JSON subset of YAML (`Mixin.read`).

Before anything is forged, the example shows what a forged mixin may not
declare: the library refuses it where it is written, with the kit and the
reason (`InvalidKitError`), rather than sending the daemon a kit it would half
apply. A mixin directory that does not exist is no refusal of the kit, but a
file of the host that cannot be read (`HostFileError`).

The package is forged in memory, its images too: nothing is written on the
host (`KitPackage.dir` is `None`), and it is tied to the API of the daemon it
was forged for (`compiled_api`), not to an `sbx` version. The sandbox created
from it runs both mixins; the daemon applies the network rules of the first
as rules of the sandbox, and removes them with it. The same kit is then
forged into a directory, `examples/target/forged/shell-forge`, replaced at
every run, its images files of that directory, and opened again from it, as
a later process does (a `KitCache` given a directory keeps its packages that
way). The images of the base kit and of the mixins stay on the daemon, as the
kit images of the other examples do.

Run it with:

    just example shell-forge
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import common
import fastsandbox
from fastsandbox import Kit, KitDescriptor, KitForge, KitPackage, LifecycleStep, Mixin
from fastsandbox.exceptions import HostFileError, InvalidKitError

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastsandbox import Client, Sandbox

EXAMPLES = Path(__file__).resolve().parent
"""The directory of the examples."""

OUTPUT = EXAMPLES / "target" / "forged" / "shell-forge"
"""Where the package is forged into the second time."""

JSON_MIXIN = EXAMPLES / "kits" / "json-mixin"
"""The mixin read from its directory."""

INSTALLED = "/home/agent/forged-tools.txt"
"""The file the install command of the Python mixin writes."""

STARTED = "/tmp/forged-tools-started.txt"
"""The file the startup command of the Python mixin writes."""

JSON_MARKER = "/home/agent/json-mixin.txt"
"""The file the install command of the JSON mixin writes."""

ALLOWED = "docs.example.com:443"
"""The host the Python mixin allows, in a reserved domain; the example never calls it."""

DENIED = "ads.example.com"
"""The host the Python mixin denies."""

STARTUP_WAIT = 10
"""How long the startup command, run in the background, may take, in seconds."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    refusals()

    tools = tools_mixin()
    print("the mixin written in Python, as its spec.yaml:")
    print(tools.descriptor.to_spec())
    # A descriptor can be read and inspected alone, without forging.
    descriptor = KitDescriptor.read(JSON_MIXIN / "spec.yaml")
    print(f"the descriptor of {descriptor.display_name}: version {descriptor.version}")
    read = Mixin.read(JSON_MIXIN)
    print(f"the mixin read from its directory: {read.name}, listed as {read.reference}")

    kit = Kit(base="shell", mixins=(tools, read))
    print(
        f"forging the {kit.label} kit: the shell kit rebuilt from its image, then both mixins",
        file=sys.stderr,
    )
    package = await KitForge(client).forge(kit)
    describe(package, client)

    name = fastsandbox.unique_name("example-forge")
    rule = f"kit:{name}"
    creation = client.create(name, kit=package)
    async with creation as sandbox, sandbox.running():
        common.report_withheld(creation.created)
        await check_mixins(sandbox)
        common.expect(
            await has_rule(client, rule, ALLOWED), "the daemon did not apply the allow rule"
        )
        common.expect(
            await has_rule(client, f"{rule}:deny", DENIED), "the daemon did not apply the deny rule"
        )
        print(
            f"the daemon applied the network rules of the mixin: {rule} allows {ALLOWED}, "
            f"{rule}:deny denies {DENIED}"
        )
    common.expect(not await has_rule(client, rule, ALLOWED), "the rule outlived its sandbox")
    print("the daemon removed the rules with the sandbox")

    await kept(client, kit, package)


def refusals() -> None:
    """Shows what a forged mixin may not declare, each refused with its kit and its reason."""
    credential = {
        "schemaVersion": "3",
        "kind": "mixin",
        "displayName": "Credential",
        "capabilities": [
            {"type": "com.docker.sandbox/credential@1", "config": {"service": "example"}}
        ],
    }
    refused("a credential", lambda: KitDescriptor.from_json(credential))
    yaml = 'schemaVersion: "3"\nkind: mixin\ndisplayName: YAML\n'
    refused("a spec.yaml in YAML", lambda: KitDescriptor.parse(yaml))
    nothing = KitDescriptor.mixin("Nothing").with_install(LifecycleStep(command="  "))
    refused(
        "a step without a command", lambda: Mixin(reference="/kits/nothing", descriptor=nothing)
    )
    # The hosts of a mixin are checked as those of a network rule are.
    url = KitDescriptor.mixin("URL").with_network_allow("https://docs.example.com")
    refused("a host written as a URL", lambda: Mixin(reference="/kits/url", descriptor=url))

    # A directory that does not exist is no refusal of the kit: the error is
    # the one of a file of the host.
    try:
        Mixin.read(JSON_MIXIN.with_name("json-mixin-missing"))
    except HostFileError as error:
        print(f"not read, a missing mixin directory: {error}")
    else:
        raise common.ExampleError("a missing mixin directory was read")


def refused(what: str, make: Callable[[], object]) -> None:
    """Checks that `make` raises `InvalidKitError`, and prints its kit and its reason."""
    try:
        make()
    except InvalidKitError as error:
        print(f"refused, {what}: kit {error.kit}, {error.reason}")
    else:
        raise common.ExampleError(f"{what} was accepted")


def tools_mixin() -> Mixin:
    """The mixin written in Python: an install command, a startup command and network rules."""
    install = (
        LifecycleStep(
            command=(
                f"echo 'forged tools installed' > {INSTALLED}; "
                f'echo "gateway: ${{MCP_GATEWAY_URL:-none}}" >> {INSTALLED}'
            )
        )
        .as_user("agent")
        .with_description("Writes the marker of the forged tools")
        # Install commands run in an emptied environment: the step names the
        # variables it needs.
        .with_gateway_env()
    )
    startup = LifecycleStep(command=f"date > {STARTED}").as_user("agent").in_background()
    descriptor = (
        KitDescriptor.mixin("Forged tools")
        .with_description("Mixin of the fastsandbox examples, written in Python")
        .with_version("0.1.0")
        .with_network_allow(ALLOWED)
        .with_network_deny(DENIED)
        .with_install(install)
        .with_startup(startup)
    )
    # Checked by the rules of the forge as it is made.
    return Mixin(reference="/kits/forged-tools", descriptor=descriptor)


def describe(package: KitPackage, client: Client) -> None:
    """Prints what the package forged in memory holds, and checks that nothing was written."""
    common.expect(package.dir is None, f"the package was written to {package.dir}")
    common.expect(package.compiled_with is None, "the package was compiled by the sbx CLI")
    common.expect(
        package.compiled_api == client.health.api_version,
        f"the package was forged for the API {package.compiled_api}",
    )
    print(
        f"the package holds {len(package.kit_refs)} kits, compiled by no sbx, "
        f"for the daemon API {package.compiled_api}:"
    )
    for reference in package.kit_refs:
        print(f"  {reference}")
    for image in package.images:
        common.expect(image.path is None, f"the image {image.reference} is a file")
        print(f"  image {image.reference or '(no reference)'}, in memory")
    # A package is a creation request and the images it needs, loaded into
    # the daemon before the request is sent.
    request = package.request("example")
    common.expect(request.name == "example", f"the request creates {request.name}")
    common.expect(
        len(request.kit_artifacts) == len(request.kits), "a kit of the request has no artifact"
    )
    print(
        f"its creation request is one for the {request.agent} agent with these kits and their "
        f"{len(request.kit_artifacts)} artifacts"
    )


async def check_mixins(sandbox: Sandbox) -> None:
    """Checks that the commands of both mixins ran in `sandbox`."""
    installed = (await output(sandbox, f"cat {INSTALLED}")).splitlines()
    common.expect(installed[:1] == ["forged tools installed"], "the install command did not run")
    gateway = installed[1] if len(installed) > 1 else "gateway: unknown"
    print(f"the install command of the Python mixin ran, and saw the MCP {gateway}")

    # The startup command runs in the background: wait for its file.
    tries = STARTUP_WAIT * 2
    started = await output(
        sandbox,
        f"for i in $(seq {tries}); do [ -s {STARTED} ] && break; sleep 0.5; done; cat {STARTED}",
    )
    common.expect(bool(started.strip()), "the startup command did not run")
    print(f"its startup command ran in the background, at {started.strip()}")

    marker = await output(sandbox, f"cat {JSON_MARKER}")
    common.expect(marker == "json-mixin installed\n", "the JSON mixin did not run")
    print(f"the install command of the JSON mixin ran: {marker.strip()}")


async def output(sandbox: Sandbox, script: str) -> str:
    """The standard output of `script`, run with `sh -c` in `sandbox`."""
    return (await sandbox.exec(["sh", "-c", script], check=True)).stdout


async def has_rule(client: Client, rule: str, host: str) -> bool:
    """Whether the daemon holds the network rule `rule` for `host`."""
    bare = host.split(":", 1)[0]
    rules = (await client.policy.rules()).rules
    return any(r.name == rule and any(bare in resource for resource in r.resources) for r in rules)


async def kept(client: Client, kit: Kit, forged: KitPackage) -> None:
    """Forges `kit` into `OUTPUT`, then opens it again from there, as a later process does.

    The package kept holds what `forged`, the one forged in memory, holds.
    """
    saved = await KitForge(client).forge(kit, output=OUTPUT)
    common.expect(saved.dir is not None and saved.dir.resolve() == OUTPUT, "written elsewhere")
    elsewhere = images_outside(saved, OUTPUT)
    common.expect(not elsewhere, f"images not kept in {OUTPUT}: {', '.join(elsewhere)}")
    print(
        f"the same kit forged into {OUTPUT.relative_to(EXAMPLES)}: "
        f"its {len(saved.images)} images are files of that directory"
    )
    opened = KitPackage.open(OUTPUT)
    common.expect(
        opened.kit_refs == forged.kit_refs, "the package kept holds other kits than in memory"
    )
    common.expect(
        references(opened) == references(forged),
        "the package kept holds other images than in memory",
    )
    common.expect(
        opened.compiled_api == client.health.api_version,
        "the package opened does not suit the daemon",
    )
    print(
        f"opened again from it, without forging: {len(opened.kit_refs)} kits, for the API "
        f"{opened.compiled_api} the daemon speaks"
    )


def images_outside(package: KitPackage, directory: Path) -> list[str]:
    """The images of `package` that are not files of `directory`."""
    return [
        image.reference or "(no reference)"
        for image in package.images
        if image.path is None
        or not Path(image.path).resolve().is_relative_to(directory)
        or not Path(image.path).is_file()
    ]


def references(package: KitPackage) -> list[str | None]:
    """The references of the images of `package`, in order."""
    return [image.reference for image in package.images]


if __name__ == "__main__":
    common.main(main)
