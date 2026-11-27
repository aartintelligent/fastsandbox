# Tasks

Full page: https://aartintelligent.github.io/fastsandbox/framework/tasks/

## API

```text
FastSandbox(name="fastsandbox", *, lifespan=None, kit="shell", kits=None,
            client=None, socket=None, max_concurrency=None)

@app.task                      # bare
@app.task(name=None, kit=None, network=None, timeout=None, env=None,
          cpus=None, memory=None, keep=False, description=None,
          max_concurrency=None)
```

`FastSandbox`:

| Argument | Default | What it does |
|---|---|---|
| `name` | `"fastsandbox"` | Prefix of the names of its sandboxes. |
| `lifespan` | None | Runs around the life of the application; what it yields is `ctx.state` (see lifespan.md). |
| `kit` | `"shell"` | The kit of the tasks that name none. |
| `kits` | the cache of the process | The `KitCache` kits come from: forged without the `sbx` CLI and kept in memory by default. |
| `client` | None | A connected `Client`, used instead of connecting. |
| `socket` | None | The socket to connect to when `client` is not given; else the socket of `sbx`. |
| `max_concurrency` | None | How many runs of any task may hold a sandbox at once. |

`@app.task` options:

| Option | Default | What it does |
|---|---|---|
| `name` | the function name | The name the task is run by. A second task of the same name raises `TaskError`. |
| `kit` | the kit of the application | A kit name (`"shell"`), a `Kit` composed with mixins and arguments, or a `KitPackage` already made. |
| `network` | no rule | A `Network` value: rules of its sandbox only (see network.md). |
| `timeout` | None | Deadline of the function: seconds, a `timedelta`, or a duration string. |
| `env` | None | Environment variables of the sandbox, a `dict[str, str]`. |
| `cpus` | the daemon's | Number of virtual CPUs. |
| `memory` | the daemon's | Memory limit in `sbx` notation, e.g. `"4g"`. |
| `keep` | `False` | Keeps the sandbox after the run, for debugging. |
| `description` | the docstring | The documentation of the task, shown by `fastsandbox tasks`. |
| `max_concurrency` | None | How many runs of this task may run at once. |

A run waits for a free slot of both concurrency bounds before it creates its
sandbox. The sandbox of a run is named from the application and the task,
lowercased, with a random suffix: `builds-describe-sandbox-1a2b3c4d`
(`fastsandbox.unique_name(prefix)` builds such names).

**Timeouts.** A number of seconds, a `datetime.timedelta`, or a string made of
`<number><unit>` parts with the units `ms`, `s`, `m`, `h`, `d`: `"500ms"`,
`"90s"`, `"10m"`, `"1h30m"`. An unreadable string raises `ValueError` when the
task is declared. The deadline bounds the call of the function only; past it
the run raises `SandboxTimeoutError` with `after` set, and deletes the sandbox.

**Synchronous tasks.** A plain `def` runs in a worker thread. The sandbox
methods are coroutines: run them with `ctx.wait(awaitable)`, which runs the
awaitable on the event loop of the run and returns its result.

**The context.** `ctx: Context` gives:

| Attribute | Value |
|---|---|
| `ctx.sandbox` | the `Sandbox` of the run |
| `ctx.client` | the `Client` of the daemon |
| `ctx.task`, `ctx.app` | the `Task` and the application |
| `ctx.state` | what the lifespan yielded |
| `ctx.run_id` | a unique identifier of the run |
| `ctx.logger` | the logger of the task |
| `ctx.agent` | the `AgentRunner`, for a task declared with `@app.agent` only; `TaskError` otherwise |
| `ctx.log(message, level=logging.INFO)` | logs with the names of the task and the sandbox |
| `await ctx.report_progress(progress, total=None, message=None)` | sends progress to the `on_progress` of the caller |
| `ctx.wait(awaitable)` | runs an awaitable from a synchronous task |

**The `Task` object.** The decorator returns a `Task`:

- `await task(**inputs)` runs it through its application, as
  `await app.run(task, **inputs)` does;
- attributes: `app`, `name`, `fn`, `description`, `kit`, `network`, `timeout`
  (seconds or None), `env`, `cpus`, `memory`, `keep`, `agent`,
  `allow_agent_hosts`, `input_model`, `output`;
- `task.input_schema`, `task.output_schema`: JSON schemas of the inputs and of
  the result (None without a return annotation);
- `app.tasks` is a `dict` of the tasks by name; `app.get_task(name)` returns
  one or raises `TaskError` listing the tasks there are.

## Example

```python
from fastsandbox import Context, FastSandbox, Network

app = FastSandbox("builds", kit="shell", max_concurrency=4)


@app.task(
    name="describe-sandbox",
    network=Network.allow("pypi.org"),
    timeout="5m",
    env={"STAGE": "ci"},
    cpus=2,
    memory="4g",
    max_concurrency=2,
)
async def describe(ctx: Context) -> dict[str, str]:
    """Reports the processors and the environment the sandbox was given."""
    cpus = await ctx.sandbox.exec("nproc", check=True)
    stage = await ctx.sandbox.exec(["printenv", "STAGE"], check=True)
    ctx.log(f"described with {cpus.stdout.strip()} CPUs")
    return {"cpus": cpus.stdout.strip(), "stage": stage.stdout.strip()}


@app.task
def disk_usage(ctx: Context, path: str = "/") -> str:
    """The disk usage of a directory of the sandbox, from synchronous code."""
    output = ctx.wait(ctx.sandbox.exec(["du", "-sh", path], check=True))
    return output.stdout.strip()
```

## Gotchas

- `@app.task` is used bare or called with keyword options; `@app.agent(...)`
  is always called (see the `agents` skill).
- `exec` does not raise on a non-zero exit code unless `check=True`; read
  `output.ok` / `output.exit_code` otherwise.
- `env` values are visible inside the sandbox: never put a secret there. Agent
  credentials are pushed as secrets by `@app.agent` instead.
- `keep=True`: the sandbox stops once nothing holds a session on it, and is
  yours to delete (`sbx`, or `await client.sandbox(name).delete()`). Log its
  name with `ctx.log(ctx.sandbox.name)` to find it.
- With a synchronous task, the call that times out keeps running in its thread,
  and its calls to the deleted sandbox fail.
- A task declared inside a function can name local dependencies in its
  annotations: the decorator resolves them in the namespace it is called from.
