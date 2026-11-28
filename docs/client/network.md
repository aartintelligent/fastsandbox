# Network and policy

Every connection a sandbox opens goes through a proxy that applies the network
policy of the daemon: rules that allow or deny hosts, or HTTP methods and
paths, for every sandbox or for one. This page covers the rules of one
sandbox, the changes of the policy, the global rules, and how a program checks
the policy and reads what the sandboxes reached.

!!! warning "The default policy"
    The default policy of `sbx` may allow everything. Give unattended code,
    agents above all, the rules it needs, and read the activity log
    afterwards.

## The rules of one sandbox

A sandbox handle changes the rules of that sandbox only, and they go with it
when it is deleted.

```python title="docs_src/client/network.py" hl_lines="9 10 14-19 20"
--8<-- "docs_src/client/network.py"
```

| Call | What it does |
|---|---|
| [`allow_hosts(*hosts)`][fastsandbox.Sandbox.allow_hosts] | allows TCP connections to the hosts or patterns (`*.githubusercontent.com`) |
| [`deny_hosts(*hosts)`][fastsandbox.Sandbox.deny_hosts] | denies TCP and UDP connections to them |
| [`remove_hosts(*hosts)`][fastsandbox.Sandbox.remove_hosts] | removes the rules added for them |
| [`remove_network_rule(id)`][fastsandbox.Sandbox.remove_network_rule] | removes one rule of the sandbox, by identifier |
| [`network_rules()`][fastsandbox.Sandbox.network_rules] | the rules scoped to the sandbox, as [`NetworkRule`][fastsandbox.models.NetworkRule] |

Each change returns a [`RuleChangeResult`][fastsandbox.models.RuleChangeResult],
whose `created` list holds the identifiers of the new rules; a change the
daemon refuses raises
[`OperationFailedError`][fastsandbox.exceptions.OperationFailedError]. From
inside the sandbox, a denied host is answered by the proxy, with HTTP 403,
in place of the host.

## Changing the policy

[`client.policy`][fastsandbox.Policy] applies any change, built with the class
methods of [`RuleChange`][fastsandbox.models.RuleChange]:

| Change | Rule |
|---|---|
| `RuleChange.allow(*hosts)` | allow TCP |
| `RuleChange.deny(*hosts)` | deny TCP and UDP |
| `RuleChange.allow_http(*hosts)`, `RuleChange.deny_http(*hosts)` | allow or deny HTTP requests |
| `RuleChange.remove(*hosts)` | remove the rules added for the hosts |
| `RuleChange.remove_rule(id)` | remove a rule by identifier |

and narrowed with `with_protocols()`, `with_methods("POST")`,
`with_path("/admin/**")` for HTTP rules, and `for_sandbox(name)`, which scopes
the change to one sandbox.

### The hosts a rule names

The hosts of a rule are checked as the `sbx` CLI checks them, before anything
is sent. A host is one of these forms:

- an exact domain, `example.com`, with globs inside its labels: `?` for one
  character, `[12]` or `[!1]` for a class;
- leading wildcard labels, `*.example.com` for one label, `**.example.com`
  for any number, and `**` alone for every host;
- an IPv4 address, or a CIDR prefix, `10.0.0.0/8` or `2001:db8::1/128`;
- any of those with a port, `example.com:443`; an IPv6 address takes its port
  in brackets, `[2001:db8::1]:443`.

Any other host raises
[`InvalidRequestError`][fastsandbox.exceptions.InvalidRequestError] with the
reason, and the daemon receives nothing: a URL (`https://api.example.com`), a
host with a path (`api.example.com/v1`, which an HTTP rule takes apart with
`with_path()`), a bare `*`, a bare IPv6 address. The daemon would store a URL
or a path as the resource of a rule and never apply it, leaving reachable the
host it seems to name. The check covers every change: `apply()`,
`apply_all()`, the rules of a sandbox handle and those of a
[task](../framework/network.md). A removal is not checked, so that a rule
stored otherwise can still go.

The daemon answers a batch of changes with HTTP 200 and reports the changes
that failed inside it:
[`apply(*changes)`][fastsandbox.Policy.apply] returns a result per change,
each with [`is_applied`][fastsandbox.models.RuleChangeResult.is_applied] and
[`check()`][fastsandbox.models.RuleChangeResult.check];
[`apply_all(*changes)`][fastsandbox.Policy.apply_all] raises
[`OperationFailedError`][fastsandbox.exceptions.OperationFailedError] on the
first that failed.

## Global rules

A change without `for_sandbox()` is global: it applies to every sandbox of the
user, now and later. A program that adds one removes it when it is done, by
the identifier returned at its creation, with
[`policy.remove_rule(id)`][fastsandbox.Policy.remove_rule].

```python
results = await client.policy.apply_all(RuleChange.deny("tracker.example"))
rule_ids = [rule.rule_id for result in results for rule in result.created]
try:
    ...
finally:
    for rule_id in rule_ids:
        await client.policy.remove_rule(rule_id)
```

A rule scoped to a sandbox is not found by the global removal: remove it
through the sandbox, with `remove_network_rule()`.

## Checking and watching

| Call | Gives |
|---|---|
| [`policy.rules()`][fastsandbox.Policy.rules] | every rule, global and scoped, as [`NetworkRules`][fastsandbox.models.NetworkRules], with whether an organization policy governs them |
| [`policy.check(check)`][fastsandbox.Policy.check] | what the policy decides for `NetworkCheck.host("host:443")` or `NetworkCheck.http("GET", url)`: a [`CheckResult`][fastsandbox.models.CheckResult] with `allowed` and the deciding `rule` |
| [`policy.log()`][fastsandbox.Policy.log] | the hosts the sandboxes reached or were refused, as a [`NetworkLog`][fastsandbox.models.NetworkLog]; [`for_sandbox(name)`][fastsandbox.models.NetworkLog.for_sandbox] keeps one sandbox |
| [`policy.profiles()`][fastsandbox.Policy.profiles] | the governance profiles |
| [`policy.setup_needed()`][fastsandbox.Policy.setup_needed] | whether the policy still needs its initial setup, done with the `sbx` CLI |
| [`policy.refresh()`][fastsandbox.Policy.refresh] | reloads the policy |

## In a FastSandbox task

A task declares its rules with [`Network`][fastsandbox.Network], scoped to its
sandbox and applied once it runs: see [Network rules](../framework/network.md).
