"""The policy beyond the hosts of one sandbox: global rules, failures, host paths, prompts.

`shell-network` shows the hosts of one sandbox; this example shows the rest of
the policy: global rules, protocols, rules removed by identifier, failures the
daemon reports inside a success, the reload of the policy, permissions on host
paths, and the stream of approval prompts.

- A **global** rule applies to every sandbox. The example adds one, a deny of
  TCP to a host of the reserved `.invalid` domain, which no real traffic
  reaches, checks it, then removes it by identifier: whatever happens, the
  global policy ends as it began.
- The daemon answers a batch of rule changes with HTTP 200 and reports a
  failed change inside: `RuleChangeResult.is_applied` and `check()` tell it.
- A host a rule cannot name is refused by the library, as the CLI refuses
  it, before anything is sent (`InvalidRequestError`, not the
  `InvalidInputError` of the daemon): a bare `*`, a bare IPv6 address, and
  the URL and path forms the daemon would store but never apply.
- A rule scoped to a sandbox, for a host or for an HTTP method and path, is
  removed through that sandbox: the global removal does not find it.
- A host path permission (`Sandbox.allow_host_path`) is a grant, listed with
  the runtime mounts of the sandbox, not a mount.
- Approval prompts (`Prompts.subscribe`) start with a `synced` line; an
  unknown prompt cannot be answered.

Run it with:

    just example shell-policy
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import common
import fastsandbox
from common import kit
from fastsandbox import NotFoundError, SandboxError
from fastsandbox.exceptions import InvalidInputError, InvalidRequestError, OperationFailedError
from fastsandbox.models import NetworkCheck, Protocol, RuleChange

if TYPE_CHECKING:
    from fastsandbox import Client, Policy, Sandbox

GLOBAL_HOST = "example-global-rule.invalid"
"""Host of the global rule, in a domain reserved to never resolve."""

SANDBOX_HOST = "example-sandbox-rule.invalid"
"""Host allowed for the sandbox only."""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    policy = client.policy
    rules = await policy.rules()
    global_rules = sum(1 for rule in rules.rules if rule.scope == "global")
    governance = "active" if rules.governance_active else "inactive"
    print(f"{len(rules.rules)} rules, {global_rules} of them global, governance {governance}")

    await global_rule(policy)
    await failed_change(policy)
    await refused_hosts(policy)
    await policy.refresh()
    print("policy reloaded")

    package = await kit.package(client, "shell")
    name = fastsandbox.unique_name("example-policy")
    async with client.create(name, kit=package) as sandbox, sandbox.running():
        await sandbox_rule(policy, sandbox)
        await host_path(sandbox)
    await prompts(client)


async def global_rule(policy: Policy) -> None:
    """Adds a global deny of TCP to `GLOBAL_HOST`, checks it, and removes it by identifier.

    The rule is removed also when the check fails: the global policy ends as
    it began.
    """
    change = RuleChange.deny(GLOBAL_HOST).with_protocols(Protocol.TCP)
    results = await policy.apply_all(change)
    created = [rule for result in results for rule in result.created]
    for rule in created:
        protocols = ", ".join(rule.protocols)
        print(f"global rule {rule.rule_id} added: deny {rule.resource} over {protocols}")
    try:
        check = await policy.check(NetworkCheck.host(f"{GLOBAL_HOST}:443"))
        common.expect(not check.allowed, f"{GLOBAL_HOST} is allowed")
        print(f"check of {GLOBAL_HOST}:443: denied by {check.rule or 'a rule'}")
    finally:
        for rule in created:
            await policy.remove_rule(rule.rule_id)
        print("global rule removed by identifier")


async def failed_change(policy: Policy) -> None:
    """Asks for the removal of a rule that does not exist.

    The daemon answers with a success that holds the failure: `apply` returns
    it, where `apply_all` would raise.
    """
    results = await policy.apply(RuleChange.remove_rule("example-no-such-rule"))
    common.expect(bool(results), "no result")
    result = results[0]
    common.expect(not result.is_applied, "a missing rule was removed")
    try:
        result.check()
    except OperationFailedError as error:
        print(f"removal of a missing rule: HTTP 200, the change failed: {error}")
    else:
        raise common.ExampleError("the failed change is a success")


async def refused_hosts(policy: Policy) -> None:
    """Shows the hosts a rule cannot name, each refused with its reason before it is sent.

    The daemon, which would store the URL and path forms and never apply them,
    receives none of them. Should one be accepted, its rule is removed before
    the example fails: the global policy ends as it began.
    """
    for host in ("*", "2001:db8::1", "https://api.example.com", "api.example.com/v1"):
        try:
            results = await policy.apply(RuleChange.allow(host))
        except InvalidInputError:
            raise common.ExampleError(f"the rule for {host} reached the daemon") from None
        except InvalidRequestError as error:
            print(f"host refused before it was sent: {error}")
            continue
        for result in results:
            for created in result.created:
                await policy.remove_rule(created.rule_id)
        raise common.ExampleError(f"a rule for {host} was accepted")
    print("a rule names host, *.domain, **, host:port, an IPv4 address, a CIDR or [IPv6]:port")


async def sandbox_rule(policy: Policy, sandbox: Sandbox) -> None:
    """Adds sandbox rules, shows that the global removal misses them, and removes them.

    `SANDBOX_HOST` is allowed for `sandbox` and listed; its global removal
    fails, and its removal through the sandbox succeeds. Then an HTTP rule,
    narrowed to a method and a path, goes the same way.
    """
    result = await sandbox.allow_hosts(SANDBOX_HOST)
    common.expect(bool(result.created), "no rule created")
    rule_id = result.created[0].rule_id
    listed = await sandbox.network_rules()
    common.expect(
        any(rule.id == rule_id and rule.is_for_sandbox(sandbox.name) for rule in listed),
        "the rule is not listed for the sandbox",
    )
    print(f"sandbox rule {rule_id} added: allow {SANDBOX_HOST}")
    try:
        await policy.remove_rule(rule_id)
    except SandboxError as error:
        print(f"its global removal fails: {error}")
    else:
        raise common.ExampleError("the global removal found a sandbox rule")
    (await sandbox.remove_network_rule(rule_id)).check()
    print("removed through the sandbox")

    # An HTTP rule, narrowed to a method and a path, for this sandbox only.
    http = (
        RuleChange.allow_http(SANDBOX_HOST)
        .with_methods("GET")
        .with_path("/v1/**")
        .for_sandbox(sandbox.name)
    )
    results = await policy.apply_all(http)
    ids = [created.rule_id for result in results for created in result.created]
    rule = next((rule for rule in await sandbox.network_rules() if rule.id in ids), None)
    if rule is None:
        raise common.ExampleError("the HTTP rule is not listed")
    targets = ", ".join(f"{target.host}{target.path or ''}" for target in rule.http_targets)
    print(f"HTTP rule {rule.id} added: {rule.decision} {','.join(rule.methods)} {targets}")
    for created_id in ids:
        (await sandbox.remove_network_rule(created_id)).check()
    print("HTTP rule removed through the sandbox")


async def host_path(sandbox: Sandbox) -> None:
    """Grants `sandbox` a host directory made for the run, then revokes it.

    The path must exist on the host: the daemon refuses another one. The
    directory is removed afterwards.
    """
    directory = _host_directory()
    try:
        await grant_and_revoke(sandbox, directory)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def _host_directory() -> str:
    """Makes an empty directory of the host for the run, and returns its real path.

    The real path, since the daemon compares the paths it grants as they are:
    on macOS the temporary directory is reached through a symbolic link.
    """
    directory = tempfile.mkdtemp(prefix=f"example-host-path-{os.getpid()}-")
    return os.fspath(Path(directory).resolve())


async def grant_and_revoke(sandbox: Sandbox, path: str) -> None:
    """Grants `sandbox` the host path `path`, then revokes it.

    The runtime mounts of the sandbox are read after each change.
    """

    async def granted() -> bool:
        """Whether the runtime mounts of the sandbox list `path`."""
        info = await sandbox.inspect()
        return any(mount.host_path == path for mount in info.runtime_mounts)

    await sandbox.allow_host_path(path)
    print(f"host path granted, listed with the runtime mounts: {await granted()}")
    await sandbox.revoke_host_path(path)
    common.expect(not await granted(), "the grant is still listed")
    print("revoked: no longer listed")


async def prompts(client: Client) -> None:
    """Reads the prompt stream until its `synced` line, and answers a prompt that does not exist."""
    pending = 0
    async with await client.prompts.subscribe() as stream:
        async for event in stream:
            if event.is_synced:
                break
            pending += 1
        else:
            raise common.ExampleError("the prompt stream ended")
    print(f"prompt stream synced, {pending} prompts pending")
    try:
        await client.prompts.respond("example-no-such-prompt", "allow")
    except NotFoundError:
        print("an unknown prompt cannot be answered: not found")
    else:
        raise common.ExampleError("an unknown prompt was answered")


if __name__ == "__main__":
    common.main(main)
