# Dependencies

Full page: https://aartintelligent.github.io/fastsandbox/framework/dependencies/

## API

**Injection by annotation.** A parameter annotated with one of these types
(or a subclass) is injected, never an input; its name does not matter:

| Annotation | Receives |
|---|---|
| `Context` | the context of the run (`sandbox`, `client`, `task`, `app`, `state`, `run_id`, `logger`) |
| `Sandbox` | the sandbox of the run, `ctx.sandbox` |
| `Client` | the client of the daemon, `ctx.client` |
| `AgentRunner` | the agent, `ctx.agent`, for a task declared with `@app.agent` |

**`Depends(dependency, use_cache=True)`**, in `Annotated[T, Depends(fn)]`,
calls `fn` for each run and passes what it gives:

- `fn` is a `def` or `async def` that returns the value, or a generator, plain
  or async, that yields it once; the code after `yield` runs when the task has
  ended, before the sandbox is deleted;
- its own parameters can only be injected ones: the annotations above and
  other `Depends`; a plain parameter makes the run raise `TaskError`;
- dependencies are resolved in the order of the parameters, after the sandbox
  is ready (network rules applied, uploads copied) and before the timeout of
  the task starts;
- `use_cache=True`: one value per function per run, shared by every parameter
  that depends on it; `use_cache=False` calls it again for each parameter.

## Example

```python
from collections.abc import AsyncIterator
from typing import Annotated

from fastsandbox import Context, Depends, FastSandbox, Sandbox

app = FastSandbox("deps")


async def python_version(sandbox: Sandbox) -> str:
    output = await sandbox.exec(["python3", "--version"], check=True)
    return output.stdout.strip()


async def scratch_dir(sandbox: Sandbox) -> AsyncIterator[str]:
    output = await sandbox.exec(["mktemp", "-d"], check=True)
    path = output.stdout.strip()
    try:
        yield path
    finally:
        await sandbox.exec(["rm", "-rf", path])


async def input_file(sandbox: Sandbox, scratch: Annotated[str, Depends(scratch_dir)]) -> str:
    path = f"{scratch}/input.txt"
    await sandbox.write_file(path, "one\ntwo\nthree\n")
    return path


@app.task(kit="shell")
async def count_lines(
    ctx: Context,
    version: Annotated[str, Depends(python_version)],
    path: Annotated[str, Depends(input_file)],
    scratch: Annotated[str, Depends(scratch_dir)],
) -> dict[str, str]:
    """Counts the lines of a file that dependencies prepared."""
    output = await ctx.sandbox.exec(["wc", "-l", path], check=True)
    return {"python": version, "lines": output.stdout.split()[0], "scratch": scratch}
```

`input_file` and the task share one `scratch_dir` value; it is removed once the
task has ended.

## Gotchas

- When the task raised, the error is raised at the `yield` of a generator
  dependency: wrap the `yield` in `try`/`finally` for what must always run.
- A synchronous dependency runs on the event loop: keep it short, or make it
  `async`.
- Values are never shared between runs. What lives as long as the application
  (a connection, a cache) belongs to the lifespan (see lifespan.md), read as
  `ctx.state`.
- A dependency cannot take an input of the task; pass data through the
  lifespan state or compute it from the context.
