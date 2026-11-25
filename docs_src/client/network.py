import fastsandbox
from fastsandbox.models import NetworkCheck, RuleChange


async def main() -> None:
    client = await fastsandbox.connect()
    async with client.create("docs-network", kit="shell") as sandbox, sandbox.running():
        # Rules of this sandbox only: they go with it.
        await sandbox.allow_hosts("pypi.org", "files.pythonhosted.org")
        denied = await sandbox.deny_hosts("example.org")
        print(f"applied: {denied.is_applied}")

        # An HTTP rule, narrowed to a method and a path, for this sandbox.
        await client.policy.apply_all(
            RuleChange.deny_http("api.example.com")
            .with_methods("POST")
            .with_path("/admin/**")
            .for_sandbox(sandbox.name)
        )
        for rule in await sandbox.network_rules():
            print(f"{rule.decision} {', '.join(rule.resources)}")

        # What the policy decides for a host, and what the sandbox reached.
        check = await client.policy.check(NetworkCheck.host("api.anthropic.com:443"))
        print(f"api.anthropic.com allowed: {check.allowed}")
        log = (await client.policy.log()).for_sandbox(sandbox.name)
        for host in log.blocked_hosts:
            print(f"blocked: {host.host} ({host.count_since} times)")


if __name__ == "__main__":
    fastsandbox.run(main())
