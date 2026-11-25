# Control its network

Every connection a sandbox opens goes through a proxy that applies the network
policy of the daemon. An agent task adds rules of its own, for its sandbox
alone. This page takes you through the three steps that make the network of an
agent what you mean it to be: know the baseline, declare what the agent needs,
read what it reached.

## 1. Know the baseline

The rules of a task **add** to the policy of the daemon: what the sandbox
reaches without them is what that policy allows, and the default policy of
`sbx` may allow everything. An allow rule does not block the rest; a deny rule
does block its host.

Before you rely on a rule, ask the policy what it decides for a host, with
[`client.policy.check(NetworkCheck.host("example.org:443"))`][fastsandbox.Policy.check]:
the answer says whether it is allowed, and which rule decides (see
[Network and policy](../client/network.md#checking-and-watching)).

## 2. Declare what it needs

```python title="docs_src/agents/network_audit.py" hl_lines="12-14 23"
--8<-- "docs_src/agents/network_audit.py"
```

- **Lines 12 to 14**: the hosts the agent needs for this task, the package
  index and the GitHub API for `GET` requests only, named once as a
  [`Network`][fastsandbox.Network] value that other tasks can share.
- **Line 23**: the rules of the task, combined with `|`: what it needs, and a
  host to keep out.
- The hosts of the agent's own service, `api.anthropic.com` for Claude Code,
  are allowed ahead of these rules, so that a narrow set of rules does not cut
  the agent off. `allow_agent_hosts=False` applies the rules of the task alone.
- The rules are scoped to the sandbox of the run and go with it: two runs, or
  a run and the rest of the machine, do not see each other's rules.

The four kinds of rule, `allow`, `deny`, `allow_http` and `deny_http`, are on
[Network rules](../framework/network.md).

## 3. Read what it reached

**Lines 32 to 38**: after the agent, the task reads the activity log of the
policy, narrowed to its sandbox, and returns the hosts it reached and the hosts
it was refused along with its outcome. The command line prints it as JSON,
for instance:

```console
$ fastsandbox run docs_src/agents/network_audit.py upgrade --repo . --package httpx
{
  "ok": true,
  "reached": [
    "api.anthropic.com:443",
    "pypi.org:443",
    "files.pythonhosted.org:443"
  ],
  "refused": []
}
```

Read it before you trust the work: a host you did not expect is worth a look,
and a refused host often explains a failure. A refused host is answered by the
proxy, with HTTP 403, in place of the host.

!!! tip "For every agent"
    Give unattended agents the rules of what they need, and read the log
    afterwards. The [security guide](../guides/security.md#network) lists the
    other boundaries of a sandbox.
