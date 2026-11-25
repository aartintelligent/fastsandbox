"""The network policy of one shell sandbox: its hosts, the proxy answer, checks and activity.

The example asks a host from inside the sandbox, denies it for this sandbox
only and asks again: the proxy of the sandbox answers in place of the host.
It adds an HTTP rule narrowed to a method and a path, lists the rules that
apply to the sandbox, checks a host against the policy, and reads the activity
log of the proxy for the sandbox.

The rules are scoped to the sandbox and go away with it: the global policy is
left as it was.

Run it with:

    just example shell-network
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import common
import fastsandbox
from common import kit
from fastsandbox.models import NetworkCheck, RuleChange

if TYPE_CHECKING:
    from fastsandbox import Sandbox

DENIED = "example.org"
"""A host the example denies."""


async def status(sandbox: Sandbox, host: str) -> str:
    """The HTTP status `https://<host>` answers from inside `sandbox`, as `curl` reports it."""
    output = await sandbox.exec(
        ["curl", "-sS", "-m", "10", "-o", "/dev/null", "-w", "%{http_code}", f"https://{host}"]
    )
    return output.stdout


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    package = await kit.package(client, "shell")
    name = fastsandbox.unique_name("example-network")
    async with client.create(name, kit=package) as sandbox, sandbox.running():
        print(f"before: {DENIED} answers {await status(sandbox, DENIED)}")
        denied = await sandbox.deny_hosts(DENIED)
        print(f"denied with rule {denied.created[0].rule_id}")
        print(f"after: the proxy answers {await status(sandbox, DENIED)}")

        # HTTP rules narrow a host down to methods and paths.
        http = await client.policy.apply_all(
            RuleChange.deny_http("example.net")
            .with_methods("POST")
            .with_path("/admin/**")
            .for_sandbox(sandbox.name)
        )
        print(f"HTTP rule {http[0].created[0].rule_id}")

        for rule in await sandbox.network_rules():
            print(f"rule {rule.decision} on {rule.resources} ({', '.join(rule.actions)})")
        check = await client.policy.check(NetworkCheck.host("api.anthropic.com"))
        print(f"api.anthropic.com allowed: {check.allowed} (rule {check.rule})")

        log = (await client.policy.log()).for_sandbox(sandbox.name)
        for host in [*log.allowed_hosts, *log.blocked_hosts]:
            print(f"activity: {host.host} x {host.count_since}")

        await sandbox.remove_hosts(DENIED)


if __name__ == "__main__":
    common.main(main)
