"""Secrets given to a shell sandbox through the socket, and what its proxy does with them.

The example pushes two custom secrets with dummy values, one for a public echo
service and one for another host, then sends requests from the sandbox to the
echo service with a placeholder in the `Authorization` header. The service
answers with the headers it received: the proxy of the sandbox writes the
value of the echo secret in place of its placeholder, and leaves the
placeholder of the other one as it is, since the request does not go to its
host. The sandbox never holds a value: not in its environment, not in its
files. The secrets stay with the sandbox through a restart, an update without
custom secrets leaves them, and an empty list removes them.

Then come the credentials of services that `sbx` knows (`github`, `openai`,
…), as `sbx secret set <service> --sandbox` gives them: the daemon records
where each comes from, and the sandbox keeps the fixed placeholders it was
created with (`GH_TOKEN` for GitHub), never a value.

Each update gets the answer of the daemon (`CredentialsOutcome`), which names
the credentials it withholds: those a kit of the sandbox declares and the
daemon does not authorize, whose values the proxy then never injects. The
shell kit declares none, so the daemon withholds nothing, which the example
checks.

Everything goes through the socket: no `sbx secret` command, nothing stored by
the CLI, and the secrets go with the sandbox. Only the dummy values leave the
machine, to `postman-echo.com` over plain HTTP. The requests are sent by the
`get` command of `common/programs/tools.py`, copied into the sandbox.

Run it with:

    just example shell-secrets
"""

from __future__ import annotations

import json
import os
from enum import StrEnum
from typing import TYPE_CHECKING

import common
import fastsandbox
from common import kit, program
from fastsandbox.models import (
    CredentialSource,
    CredentialsUpdate,
    CustomSecret,
    ServiceCredential,
)

if TYPE_CHECKING:
    from fastsandbox import Sandbox

ECHO_HOST = "postman-echo.com"
"""Public service answering with the headers it received."""

OTHER_HOST = "api.example.com"
"""Host of the second secret, which the requests of the example never reach."""

ECHO_VALUE = "example-dummy-value-not-a-secret"
"""Dummy value of the secret of the echo service."""

ECHO_ENV = "EXAMPLE_ECHO_KEY"
"""Environment variable the echo secret names for its placeholder."""

OTHER_VALUE = "example-other-dummy-value"
"""Dummy value of the secret of the other host."""

GITHUB_VALUE = "example-github-dummy-value"
"""Dummy value of the GitHub credential."""

OPENAI_VALUE = "example-openai-dummy-value"
"""Dummy value of the OpenAI credential."""

OPENAI_SOURCE = "EXAMPLE_OPENAI_SOURCE"
"""Source recorded for the OpenAI credential.

An environment variable, as the CLI declares the credentials it stores.
"""

CANARY = "/tmp/example-search-canary"
"""File the search of the values must find, to show that it reads files."""

SEARCH_TIMEOUT = 120.0
"""How long the search of the values through the files may take, in seconds."""


class Received(StrEnum):
    """What the echo service received in place of a placeholder."""

    ECHO_VALUE = "the value of the echo secret"
    OTHER_VALUE = "the value of the other secret"
    PLACEHOLDER = "the placeholder, unchanged"
    OTHER = "something else"


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    package = await kit.package(client, "shell")
    name = fastsandbox.unique_name("example-secrets")
    async with client.create(name, kit=package) as sandbox:
        async with sandbox.running():
            tools = await program.install(sandbox, "tools")
            echo = await custom_secrets(sandbox, tools)
        # The daemon keeps the secrets of a sandbox through a restart: the
        # session is released, the sandbox stopped, and started again by a
        # new session.
        await sandbox.stop()
        async with sandbox.running():
            await expect(sandbox, tools, echo, Received.ECHO_VALUE)
            print("after a stop and a start, without a new push: still the value")
            await updates(sandbox, tools, echo)
            await services(sandbox)


async def custom_secrets(sandbox: Sandbox, tools: list[str]) -> str:
    """Pushes two custom secrets, and checks what the echo service receives and the sandbox holds.

    Returns the placeholder of the echo secret.
    """
    # The placeholders are what the sandbox sees; the values only travel over
    # the socket, to the daemon.
    echo = f"sbx-cs-echo{os.getpid()}"
    other = f"sbx-cs-other{os.getpid()}"
    secret = CustomSecret.new([ECHO_HOST], echo, ECHO_VALUE, env_name=ECHO_ENV)
    # A value a program logs by mistake shows masked; reading it takes an
    # explicit `get_secret_value()`.
    length = len(secret.value.get_secret_value())
    print(f"the value of the echo secret, as a log prints it: {secret.value} ({length} characters)")
    secrets = (
        CredentialsUpdate()
        .with_custom_secret(secret)
        .with_custom_secret(CustomSecret.new([OTHER_HOST], other, OTHER_VALUE))
    )
    outcome = await sandbox.push_credentials(secrets)
    print(f"pushed two custom secrets with dummy values, for {ECHO_HOST} and {OTHER_HOST}")
    common.expect(not outcome.withheld, f"the daemon withholds {outcome.withheld}")
    print(
        f"the daemon answers {outcome.message or 'nothing'!r} and withholds nothing: "
        "the shell kit declares no credential"
    )

    await expect(sandbox, tools, echo, Received.ECHO_VALUE)
    print(f"{ECHO_HOST} received the value of its secret in place of the placeholder")
    await expect(sandbox, tools, other, Received.PLACEHOLDER)
    print(f"it received the placeholder of the {OTHER_HOST} secret unchanged")

    environment = (await sandbox.exec(["env"], check=True)).stdout
    # The search runs as root, so that no file escapes it, and must find a file
    # written for it: an empty answer then means that no file holds a value,
    # not that none was read.
    canary = f"example-search-canary-{os.getpid()}"
    await sandbox.write_file(CANARY, f"{canary}\n")
    search = [
        "grep",
        "-rlsF",
        "--exclude-dir=proc",
        "--exclude-dir=sys",
        "--exclude-dir=dev",
        *("-e", ECHO_VALUE, "-e", OTHER_VALUE, "-e", canary),
        "/",
    ]
    files = await sandbox.exec(search, user="root", timeout=SEARCH_TIMEOUT)
    found = files.stdout.splitlines()
    common.expect(
        not any(value in environment for value in (ECHO_VALUE, OTHER_VALUE)),
        "a value is in the environment of the sandbox",
    )
    common.expect(
        found == [CANARY],
        f"the search of the files of the sandbox found {found}, not only {CANARY}",
    )
    print("the sandbox holds neither value: not in its environment, not in its files")
    # `env_name` is recorded with the secret, but the daemon puts no such
    # variable in the environment of an execution.
    common.expect(
        not any(line.startswith(f"{ECHO_ENV}=") for line in environment.splitlines()),
        f"{ECHO_ENV} is in the environment",
    )
    print(f"no {ECHO_ENV} variable either, although the secret names it")
    return echo


async def updates(sandbox: Sandbox, tools: list[str], echo: str) -> None:
    """Pushes updates without custom secrets, then with an empty list of them.

    The first leaves the secrets as they are, the second removes them: the
    echo service then receives the placeholder `echo` unchanged.
    """
    # An update that carries no custom secrets, a service credential for
    # instance, leaves them as they are: `custom_secrets` is `None`, and left
    # out of the request.
    await sandbox.push_credentials(CredentialsUpdate())
    await expect(sandbox, tools, echo, Received.ECHO_VALUE)
    print("after an update without custom secrets: still the value")

    await sandbox.push_credentials(CredentialsUpdate().without_custom_secrets())
    await expect(sandbox, tools, echo, Received.PLACEHOLDER)
    print("after an update with an empty list: the placeholder, unchanged")


async def services(sandbox: Sandbox) -> None:
    """Gives `sandbox` service credentials with dummy values, then takes them back.

    The first is given the way `sbx secret set <service> --sandbox` does, the
    second with an explicit source; what the daemon records and what the
    sandbox holds are checked at each step.
    """
    placeholder = await environment(sandbox, "GH_TOKEN")
    print(f"the sandbox was created with the placeholder GH_TOKEN={placeholder or '(none)'}")

    # `push_service_secret` is the shortcut of `sbx secret set github
    # --sandbox`: a value, and a source the CLI names after the sandbox
    # (`CredentialsUpdate.with_sandbox_secret`).
    outcome = await sandbox.push_service_secret("github", GITHUB_VALUE)
    print(
        f"the daemon answers {outcome.message or 'nothing'!r} to the github credential, "
        f"sources updated: {outcome.credential_source_updates_applied}, "
        f"withholding {outcome.withheld}"
    )
    explicit = (
        CredentialsUpdate()
        .with_service_credential("openai", OPENAI_VALUE)
        .with_credential_source("openai", CredentialSource.env(OPENAI_SOURCE))
    )
    outcome = await sandbox.push_credentials(explicit)
    common.expect(not outcome.withheld, f"the daemon withholds {outcome.withheld}")
    recorded = (await sandbox.inspect()).credential_sources
    for service, source in recorded.items():
        print(f"the daemon records the {service} credential, from {source}")
    common.expect(
        sorted(recorded) == ["github", "openai"], f"unexpected credential sources: {recorded}"
    )
    env = (await sandbox.exec(["env"], check=True)).stdout
    common.expect(
        not any(value in env for value in (GITHUB_VALUE, OPENAI_VALUE)),
        "a service credential is in the environment of the sandbox",
    )
    common.expect(await environment(sandbox, "GH_TOKEN") == placeholder, "GH_TOKEN changed")
    print("the sandbox still holds the same placeholder, and neither value")

    # `remove_service_secret` is the shortcut of `sbx secret rm github
    # --sandbox` (`CredentialsUpdate.without_sandbox_secret`); by hand, an
    # empty value and the source removed.
    await sandbox.remove_service_secret("github")
    taken_back = CredentialsUpdate(
        credential_values=[ServiceCredential.cleared("openai")]
    ).without_credential_source("openai")
    await sandbox.push_credentials(taken_back)
    recorded = (await sandbox.inspect()).credential_sources
    common.expect(not recorded, f"credentials left: {recorded}")
    print("both taken back: the daemon records no credential any more")


async def environment(sandbox: Sandbox, name: str) -> str | None:
    """The value of the environment variable `name` in an execution of `sandbox`."""
    env = (await sandbox.exec(["env"], check=True)).stdout
    prefix = f"{name}="
    return next(
        (line.removeprefix(prefix) for line in env.splitlines() if line.startswith(prefix)), None
    )


async def expect(sandbox: Sandbox, tools: list[str], placeholder: str, expected: Received) -> None:
    """Sends the placeholder to the echo service, and fails unless it received `expected`."""
    received, header = await receives(sandbox, tools, placeholder)
    if received is not expected:
        raise common.ExampleError(
            f"the echo service received {received} ({header!r}), not {expected}"
        )


async def receives(
    sandbox: Sandbox, tools: list[str], placeholder: str
) -> tuple[Received, str | None]:
    """What the echo service receives for `Authorization: Bearer <placeholder>`.

    The request is sent from the sandbox; the result also holds the bearer
    value the service saw, if any.
    """
    url = f"http://{ECHO_HOST}/headers"
    command = [*tools, "get", url, "Authorization", f"Bearer {placeholder}"]
    output = await sandbox.exec(command, check=True)
    try:
        echo = json.loads(output.stdout)
    except ValueError:
        raise common.ExampleError("the echo service does not answer with JSON") from None
    header = echo.get("headers", {}).get("authorization")
    bearer = (
        header.removeprefix("Bearer ")
        if isinstance(header, str) and header.startswith("Bearer ")
        else None
    )
    if bearer == ECHO_VALUE:
        return Received.ECHO_VALUE, bearer
    if bearer == OTHER_VALUE:
        return Received.OTHER_VALUE, bearer
    if bearer == placeholder:
        return Received.PLACEHOLDER, bearer
    return Received.OTHER, bearer


if __name__ == "__main__":
    common.main(main)
