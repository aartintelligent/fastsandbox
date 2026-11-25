# The network of an agent

Full page: https://aartintelligent.github.io/fastsandbox/agents/network/

Every connection of a sandbox goes through a proxy that applies the daemon's
network policy. A task's `network` rules are added for its sandbox alone and go
with it.

## API

| Rule | Effect |
|---|---|
| `Network.allow(*hosts)` | Allows TCP connections to the hosts or patterns |
| `Network.deny(*hosts)` | Denies TCP and UDP connections to them |
| `Network.allow_http(*hosts, methods=(), path=None)` | Allows HTTP requests, narrowed to `methods` and the path pattern |
| `Network.deny_http(*hosts, methods=(), path=None)` | Denies HTTP requests, likewise narrowed |

`|` combines rules, applied in order; a `Network` is a value that tasks can
share. `@app.agent(..., network=..., allow_agent_hosts=True)`: when `network`
is given, the hosts the agent's kit declares (`api.anthropic.com` for Claude
Code) are allowed ahead of it; `allow_agent_hosts=False` applies the task's
rules alone. Without `network`, no rule is applied.

After the run: `(await ctx.client.policy.log()).for_sandbox(ctx.sandbox.name)`
is a `NetworkLog` with `allowed_hosts` and `blocked_hosts`, each a list of
`HostActivity` (`host` as `host:port`, `count_since`, `rule`, `reason`, ...).
Before relying on a rule, `await client.policy.check(NetworkCheck.host("example.org:443"))`
says what the policy decides and which rule decides it.

## Example

```python
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel

from fastsandbox import Context, FastSandbox, Network, WorkspaceDir

app = FastSandbox("upgrades")

# What the agent needs besides its own service.
NEEDS = Network.allow("pypi.org", "files.pythonhosted.org") | Network.allow_http(
    "api.github.com", methods=["GET"]
)


class Outcome(BaseModel):
    ok: bool
    reached: list[str]
    refused: list[str]


@app.agent("claude", network=NEEDS | Network.deny("example.org"), timeout="20m")
async def upgrade(
    ctx: Context, repo: Annotated[Path, WorkspaceDir(clone=True)], package: str
) -> Outcome:
    """Has Claude Code upgrade a dependency, then reports what the sandbox reached."""
    run = await ctx.agent.prompt(
        f"Upgrade {package} to its latest version and fix what breaks.",
        working_dir=str(repo.resolve()),
    )
    log = (await ctx.client.policy.log()).for_sandbox(ctx.sandbox.name)
    return Outcome(
        ok=run.ok,
        reached=[host.host for host in log.allowed_hosts],
        refused=[host.host for host in log.blocked_hosts],
    )
```

## Gotchas

- Rules **add** to the daemon's policy, and the default policy of `sbx` may
  allow everything: an allow rule does not block the rest, a deny rule does
  block its host. Check the baseline with `client.policy.check(...)`.
- A refused host is answered by the proxy with HTTP 403, in place of the host:
  the agent sees a 403, not a connection error.
- A rule the daemon does not apply makes the run raise `OperationFailedError`
  before the task is called.
- `allow_agent_hosts=False` with narrow rules can cut the agent off its own
  service; the symptom is an agent that fails to reach its API.
- Rules are scoped to the run's sandbox: never add global rules
  (`client.policy.apply` without `for_sandbox`) from a task.
