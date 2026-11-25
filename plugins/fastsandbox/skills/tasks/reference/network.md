# Network rules

Full page: https://aartintelligent.github.io/fastsandbox/framework/network/

## API

`Network` is a frozen value holding rule changes; the `network=` option of a
task applies it to the sandbox of each run, once the sandbox runs and before
the task, scoped to that sandbox.

| Constructor | Rule |
|---|---|
| `Network.allow(*hosts)` | allows TCP connections to the hosts or patterns |
| `Network.deny(*hosts)` | denies TCP and UDP connections to them |
| `Network.allow_http(*hosts, methods=(), path=None)` | allows HTTP requests, narrowed to `methods` and to the path pattern `path` when given |
| `Network.deny_http(*hosts, methods=(), path=None)` | denies HTTP requests, likewise narrowed |
| `a \| b` | combines two values; the rules apply in order |
| `Network()` | no rule (the default of a task) |

- Hosts are names or patterns (`*.githubusercontent.com`); `path` is a pattern
  such as `/admin/**`.
- `network.changes` is the tuple of `RuleChange` values;
  `await network.apply(sandbox)` applies them to any sandbox, scoped to it.
- A rule the daemon does not apply makes the run raise
  `OperationFailedError` before the task is called.
- A denied host is answered by the proxy of the sandbox, HTTP 403, in place of
  the host: a request "succeeds" with the status of the proxy.

## Example

```python
from fastsandbox import Context, FastSandbox, Network

PYPI = Network.allow("pypi.org", "files.pythonhosted.org")
GITHUB_READ_ONLY = Network.allow_http("api.github.com", methods=["GET"])

app = FastSandbox("network")


@app.task(kit="shell", network=PYPI | GITHUB_READ_ONLY | Network.deny("example.org"))
async def probe(ctx: Context, url: str) -> str:
    """The HTTP status a URL answers from inside the sandbox."""
    output = await ctx.sandbox.exec(
        ["curl", "-sS", "-m", "10", "-o", "/dev/null", "-w", "%{http_code}", url]
    )
    return output.stdout
```

What a run reached, read after the work (inside the task):

```python
from fastsandbox import Context


async def reached_hosts(ctx: Context) -> tuple[list[str], list[str]]:
    log = (await ctx.client.policy.log()).for_sandbox(ctx.sandbox.name)
    return [h.host for h in log.allowed_hosts], [h.host for h in log.blocked_hosts]
```

## Gotchas

- **Rules add to the policy of the daemon**: what the sandbox reaches without
  them is what that policy allows, and the default policy of `sbx` may allow
  everything. An allow rule does not confine the sandbox; deny what must stay
  out, and read the activity log (`client.policy.log()`) after a run.
- Check what the policy decides for a host with
  `await client.policy.check(NetworkCheck.host("example.org:443"))`
  (`from fastsandbox import NetworkCheck`).
- Two runs, or a run and the rest of the machine, never see each other's
  rules; nothing is left behind once the sandbox is deleted.
- For an agent task, the hosts of the agent's own service are allowed ahead of
  these rules unless `allow_agent_hosts=False` (see the `agents` skill).
- A `Network` is a value: name it once (`PYPI`) and share it between tasks.
