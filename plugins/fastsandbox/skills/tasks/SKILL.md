---
name: tasks
description: Declaring and running FastSandbox applications - `FastSandbox(...)`, `@app.task`, inputs and results validated from the signature, host directories with `WorkspaceDir`, `Mounted` and `Uploaded`, network rules with `Network`, injection of `Context`, `Sandbox`, `Client` and `Depends`, lifespan and state, timeouts, synchronous tasks, progress, concurrency, `app.run`, `run_sync`, `fastsandbox.run` and the `fastsandbox` command line (`run`, `tasks`, `info`, `kits compile`, `ssh-proxy`). Load before writing or changing code that declares or runs tasks in throw-away sandboxes, or a command that runs them.
---

# Tasks

A FastSandbox application declares tasks with decorators on typed functions.
Each run of a task gets a throw-away sandbox of Docker Sandboxes: created from
the kit of the task, given its network rules and host directories, held
running while the function runs, then deleted. fastsandbox connects to the
socket of the daemon of Docker Sandboxes: it must be installed and running for
the current user (`sbx version` answers), or every run raises
`DaemonUnavailableError`.

## Essentials

- **The function runs on the host**, in the process of the caller. What runs in
  the sandbox is what it asks through `ctx.sandbox` (`exec`, `write_file`,
  `read_text`…). Nothing in the body of the function runs in the sandbox by
  itself.
- **Parameters are injected or inputs.** A parameter annotated `Context`,
  `Sandbox`, `Client` or `AgentRunner`, or `Annotated[T, Depends(fn)]`, is
  injected; every other parameter is an input.
- **Inputs are validated before anything is created**: a Pydantic model built
  from the signature, extra arguments refused. Invalid inputs raise
  `pydantic.ValidationError` and no sandbox is created. The return annotation
  validates the result, after the sandbox is deleted.
- **No `*args` or `**kwargs`**, and task names are unique: both raise
  `TaskError` when the task is declared.
- **Host directories** go in `Annotated[Path, ...]`: `WorkspaceDir()` (one per
  task, the working directory of the sandbox), `Mounted(target, read_only)`,
  `Uploaded(target)` (a copy). A mount is live: what the sandbox changes
  changes the host. Name a mounted directory inside the sandbox with
  `str(path.resolve())`.
- **Network rules add to the policy of the daemon.** `Network.allow(...)` does
  not block the other hosts; `Network.deny(...)` blocks its hosts. The rules
  are scoped to the sandbox of the run and go with it.
- **`timeout` bounds the function only**: the creation of the sandbox, its
  preparation and the dependencies come before the deadline starts. Over it,
  `SandboxTimeoutError` (`after` = the timeout in seconds). A command has its
  own `timeout=` on `ctx.sandbox.exec`.
- **A synchronous `def` task runs in a worker thread**: reach the sandbox with
  `ctx.wait(ctx.sandbox.exec(...))`. A thread cannot be interrupted: after a
  timeout it keeps running until it returns.
- **The sandbox is deleted whatever happens**, an error or a timeout included,
  unless `keep=True`: then it is left for you to inspect and to delete.
- **Start the application once for many runs** with `async with app:`: one
  client and one lifespan for every run inside. Without it, each run connects
  and enters the lifespan on its own.
- **The first run of a kit compiles it** with the `sbx` CLI (minutes for an
  agent kit); `fastsandbox kits compile shell` does it ahead of time.
- **Agent tasks** (`@app.agent("claude")`, `ctx.agent`) are covered by the
  `agents` skill; the sandbox API used through `ctx.sandbox` by the `client`
  skill; tests without a daemon by the `testing` skill.

## A complete task

```python
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel

import fastsandbox
from fastsandbox import Context, FastSandbox, Network, Uploaded

app = FastSandbox("ci")


class Report(BaseModel):
    passed: bool
    summary: str


@app.task(kit="shell", network=Network.allow("pypi.org"), timeout="10m")
async def run_tests(
    ctx: Context, repo: Annotated[Path, Uploaded("/work")], command: str = "make test"
) -> Report:
    """Runs the tests of a project in a copy of it."""
    output = await ctx.sandbox.exec(f"cd /work && {command}")
    return Report(passed=output.ok, summary=(output.stdout + output.stderr)[-500:])


if __name__ == "__main__":
    print(fastsandbox.run(run_tests, repo="."))
```

```sh
fastsandbox run app.py run_tests --repo .
```

## Map

| Need | API | Reference |
|---|---|---|
| Declare a task, its kit, CPUs, memory, environment, deadline | `@app.task(...)`, `FastSandbox(...)` | [tasks.md](reference/tasks.md) |
| Validate inputs and results, JSON schemas | the signature, `Task.input_schema`, `Task.output_schema` | [inputs-outputs.md](reference/inputs-outputs.md) |
| Give the sandbox host directories | `WorkspaceDir`, `Mounted`, `Uploaded` | [host-paths.md](reference/host-paths.md) |
| Allow or deny hosts | `Network` | [network.md](reference/network.md) |
| Get the context, the sandbox, the client, a computed value | `Context`, `Sandbox`, `Client`, `Depends` | [dependencies.md](reference/dependencies.md) |
| Share state across runs, reuse one client | `lifespan=`, `ctx.state`, `async with app:`, `client=`, `socket=` | [lifespan.md](reference/lifespan.md) |
| Run tasks, report progress, run many at once, handle errors | `app.run`, `run_sync`, `fastsandbox.run`, `ctx.report_progress`, `max_concurrency` | [running.md](reference/running.md) |
| Run from a shell | `fastsandbox run`, `tasks`, `info`, `kits compile`, `ssh-proxy` | [cli.md](reference/cli.md) |

## References

- [reference/tasks.md](reference/tasks.md): the options of a task, timeouts,
  synchronous tasks, logging and progress, the `Task` object.
- [reference/inputs-outputs.md](reference/inputs-outputs.md): what the
  signature accepts and refuses, results, schemas, inputs on the command line.
- [reference/host-paths.md](reference/host-paths.md): the three markers, clone
  mode.
- [reference/network.md](reference/network.md): building `Network` values and
  what they change.
- [reference/dependencies.md](reference/dependencies.md): injection by
  annotation, `Depends`, generator dependencies, the cache of a run.
- [reference/lifespan.md](reference/lifespan.md): the lifespan, the state,
  starting the application once, choosing the client.
- [reference/running.md](reference/running.md): the ways to run, progress,
  concurrency, the errors of a run.
- [reference/cli.md](reference/cli.md): every subcommand and option of the
  `fastsandbox` command.

Full documentation: https://aartintelligent.github.io/fastsandbox/framework/
