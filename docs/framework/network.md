# Network rules

The `network` option of a task gives the network rules of its sandbox, as a
[`Network`][fastsandbox.Network]. They are applied once the sandbox runs,
before the task, scoped to that sandbox: they add to the policy of the daemon
for this sandbox alone, and go away with it. This page shows how to build them
and what they change.

## Allowing and denying hosts

```python title="docs_src/tasks/network_rules.py" hl_lines="3 4 9"
--8<-- "docs_src/tasks/network_rules.py"
```

| Rule | What it does |
|---|---|
| [`Network.allow(*hosts)`][fastsandbox.Network.allow] | Allows TCP connections to the hosts. |
| [`Network.deny(*hosts)`][fastsandbox.Network.deny] | Denies TCP and UDP connections to the hosts. |
| [`Network.allow_http(*hosts, methods=(), path=None)`][fastsandbox.Network.allow_http] | Allows HTTP requests to the hosts, narrowed to `methods` and to the path pattern `path` when given. |
| [`Network.deny_http(*hosts, methods=(), path=None)`][fastsandbox.Network.deny_http] | Denies HTTP requests to the hosts, likewise narrowed. |

Each takes hosts or host patterns. `|` combines rules into one `Network`,
applied in order: a `Network` is a value, which can be named once, as `PYPI`
here, and shared by several tasks.

A host is written as the `sbx` CLI takes it, `example.com`, `*.example.com`
or `example.com:443` for instance
(see [The hosts a rule names](../client/network.md#the-hosts-a-rule-names)).
A URL, a host with a path, a bare `*` or a bare IPv6 address fails the run with
[`InvalidRequestError`][fastsandbox.exceptions.InvalidRequestError] when its
rules are applied, before they reach the daemon; the sandbox is deleted as
after any failure.

A denied host is answered by the proxy of the sandbox in place of the host:
`probe` then gets the status of the proxy, not an error of the connection.

## What the rules change

The rules of a task add to the policy of the daemon: what a sandbox reaches
without them is what that policy allows, and the default policy of `sbx` may
allow everything: deny rules are for hosts it would let through, allow rules
for hosts it would block. For an unattended task, and above all for an
agent, give the rules of what it needs, and read what it reached afterwards
with the activity log of the policy (see
[Network and policy](../client/network.md)).

The rules are scoped to the sandbox of the run: two runs of the same task, or a
task and the rest of the machine, do not see each other's rules. A rule that
the daemon does not apply makes the run raise
[`OperationFailedError`][fastsandbox.exceptions.OperationFailedError] before the
task is called.

For an agent task, the hosts the agent needs are allowed along with the rules
of the task: see [Agents](agents.md#the-network-of-an-agent).
