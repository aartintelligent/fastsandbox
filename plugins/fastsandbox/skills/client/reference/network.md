# Network and policy

Full page: https://aartintelligent.github.io/fastsandbox/client/network/

Every connection of a sandbox goes through a proxy that applies the network
policy of the daemon. Rules allow or deny hosts (TCP, or TCP and UDP for a
deny) or HTTP requests (methods, path patterns), for every sandbox or one.

## API

### The rules of one sandbox (they go with it)

| Call | What it does |
|---|---|
| `await sandbox.allow_hosts(*hosts) -> RuleChangeResult` | allows TCP to hosts or patterns (`*.githubusercontent.com`) |
| `await sandbox.deny_hosts(*hosts) -> RuleChangeResult` | denies TCP and UDP to them |
| `await sandbox.remove_hosts(*hosts) -> RuleChangeResult` | removes the rules added for them |
| `await sandbox.remove_network_rule(id) -> RuleChangeResult` | removes one rule of the sandbox by id |
| `await sandbox.network_rules() -> list[NetworkRule]` | the rules that apply to it |

### `client.policy` (`Policy`)

| Call | Gives |
|---|---|
| `await rules() -> NetworkRules` | `governance_active`, `rules: list[NetworkRule]` (global and scoped) |
| `await apply(*changes: RuleChange) -> list[RuleChangeResult]` | applies a batch; each result says whether it applied (the daemon answers 200 even for failed changes) |
| `await apply_all(*changes) -> list[RuleChangeResult]` | same, raises `OperationFailedError` on the first change that did not apply |
| `await remove_rule(id)` | removes a global rule by id |
| `await check(check: NetworkCheck) -> CheckResult` | what the policy decides: `allowed`, the deciding `rule`, `action`… |
| `await log() -> NetworkLog` | hosts reached (`allowed_hosts`) and refused (`blocked_hosts`), as `HostActivity` (`host`, `vm_name`, `count_since`, `last_seen`, `rule`, `reason`); `.for_sandbox(name)` keeps one sandbox |
| `await profiles() -> list[Any]` | governance profiles |
| `await setup_needed() -> bool` | whether the policy still needs its initial setup (done with the `sbx` CLI) |
| `await refresh()` | reloads the policy |

`RuleChange` (`from fastsandbox.models import RuleChange`):

| Builder | Rule |
|---|---|
| `RuleChange.allow(*hosts)` | allow TCP |
| `RuleChange.deny(*hosts)` | deny TCP and UDP |
| `RuleChange.allow_http(*hosts)`, `RuleChange.deny_http(*hosts)` | allow or deny HTTP requests |
| `RuleChange.remove(*hosts)` | remove the rules added for the hosts |
| `RuleChange.remove_rule(id)` | remove a rule by id |
| `.for_sandbox(name)` | scope the change to one sandbox |
| `.with_protocols("tcp", ...)`, `.with_methods("POST", ...)`, `.with_path("/admin/**")` | narrow it |

`RuleChangeResult`: `action`, `error`, `resources`, `sandbox_id`,
`created: list[CreatedRule]` (`rule_id`, `resource`, `protocols`),
`is_applied`, `check()` (raises `OperationFailedError`).
`NetworkCheck.host("api.example.com:443")` and
`NetworkCheck.http("GET", "https://api.example.com/v1")` build checks.

## Example

```python
import fastsandbox
from fastsandbox.models import NetworkCheck, RuleChange


async def main() -> None:
    client = await fastsandbox.connect()
    async with client.create(kit="shell") as sandbox, sandbox.running():
        await sandbox.allow_hosts("pypi.org", "files.pythonhosted.org")
        (await sandbox.deny_hosts("example.org")).check()
        await client.policy.apply_all(
            RuleChange.deny_http("api.example.com")
            .with_methods("POST")
            .with_path("/admin/**")
            .for_sandbox(sandbox.name)
        )
        await sandbox.exec("pip download --no-deps requests -d /tmp/wheels")

        decision = await client.policy.check(NetworkCheck.host("example.org:443"))
        print(f"example.org allowed: {decision.allowed} by {decision.rule}")
        log = (await client.policy.log()).for_sandbox(sandbox.name)
        print("reached:", [host.host for host in log.allowed_hosts])
        print("refused:", [host.host for host in log.blocked_hosts])

    # A global rule applies to every sandbox: remove it by id when done.
    results = await client.policy.apply_all(RuleChange.deny("tracker.example"))
    try:
        ...
    finally:
        for result in results:
            for rule in result.created:
                await client.policy.remove_rule(rule.rule_id)


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- The default policy of `sbx` may allow everything: an allow rule does not
  confine a sandbox, only deny rules block. Check the baseline with
  `policy.check()` and audit with `policy.log()` after unattended code.
- Inside the sandbox, a denied host is answered by the proxy with HTTP 403,
  not a connection error.
- A rule scoped to a sandbox is not found by `policy.remove_rule()`: remove it
  through the sandbox, `remove_network_rule(id)`.
- Global rules are shared by every sandbox and the `sbx` CLI: a program that
  adds one removes it, also on an error.
- For the rules of a FastSandbox task, use `Network` (load the tasks skill).
