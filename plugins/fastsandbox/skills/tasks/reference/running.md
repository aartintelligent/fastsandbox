# Running tasks

Full page: https://aartintelligent.github.io/fastsandbox/framework/running/

## API

| Call | From | Returns |
|---|---|---|
| `await app.run(task, /, *, on_progress=None, **inputs)` | async code; `task` is a name or a `Task` | the validated result |
| `await task(**inputs)` | async code; the `Task` the decorator returned | the same |
| `app.run_sync(task, /, **inputs)` | synchronous code (own event loop) | the same |
| `fastsandbox.run(task, **inputs)` | synchronous code | the same |
| `fastsandbox.run(coroutine)` | synchronous code: runs any awaitable with `asyncio.run` | its result |
| `fastsandbox run APP TASK --input-name value` | a shell (see cli.md) | prints the result |

- `on_progress` receives what the task reports with
  `await ctx.report_progress(progress, total=None, message=None)`: a function,
  plain or async, called with `(progress, total, message)` (type
  `ProgressHandler`, `from fastsandbox.types import ProgressHandler`). Progress
  is also logged at the debug level of the logger of the task.
- Runs are independent, each with its own sandbox: `asyncio.gather` runs
  several at once.
- Concurrency bounds: `FastSandbox(max_concurrency=n)` for every run of the
  application, `@app.task(max_concurrency=n)` for one task; a run waits for a
  free slot of both before it creates its sandbox.
- A program that runs many tasks starts the application once with
  `async with app:` (one client, one lifespan; see lifespan.md).

Errors of a run (the sandbox is deleted whatever happens, unless `keep=True`):

| Error | When |
|---|---|
| `pydantic.ValidationError` | invalid inputs, before anything is created; or a result that does not match the return annotation, after the sandbox is deleted |
| `TaskError` | no such task, or a misdeclared task: two `WorkspaceDir`, a dependency with a plain parameter, an agent kit that describes no agent |
| `SandboxTimeoutError` | the function went over the timeout of the task; `after` is the timeout in seconds |
| `CommandFailedError` | a command run with `check=True` exited non-zero; `exit_code`, `stdout`, `stderr` |
| `OperationFailedError` | a network rule of the task was not applied |
| `DaemonUnavailableError` | the daemon of Docker Sandboxes cannot be reached |
| another `SandboxError` | the daemon refused or failed an operation (`NotFoundError`, `ConflictError`…) |
| any other exception | raised by the function of the task, passed on as it is |

Every error of fastsandbox derives from `SandboxError`
(`from fastsandbox import SandboxError`); `ValidationError` is Pydantic's.

## Example

```python
import asyncio

from pydantic import ValidationError

import fastsandbox
from fastsandbox import CommandFailedError, Context, FastSandbox, SandboxTimeoutError

app = FastSandbox("digests", max_concurrency=2)


@app.task(kit="shell", timeout="2m")
async def sha256(ctx: Context, text: str) -> str:
    """The SHA-256 digest of a text, computed in a sandbox."""
    await ctx.report_progress(1, 2, "sandbox ready")
    output = await ctx.sandbox.exec(
        ["sh", "-c", 'printf %s "$1" | sha256sum', "sh", text], check=True
    )
    await ctx.report_progress(2, 2, "digest computed")
    return output.stdout.split()[0]


def show_progress(progress: float, total: float | None, message: str | None) -> None:
    print(f"{progress:g}/{total}: {message}")


async def main() -> None:
    async with app:
        print(await app.run("sha256", text="hello", on_progress=show_progress))
        digests = await asyncio.gather(*(sha256(text=text) for text in ("a", "b", "c")))
        print(digests)
        try:
            await app.run("sha256")
        except ValidationError as error:
            print(f"invalid inputs: {error.error_count()} error")
        except (CommandFailedError, SandboxTimeoutError) as error:
            print(f"failed: {error}")


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- `app.run_sync` and `fastsandbox.run` start an event loop: they cannot be
  called from a running loop (a notebook cell with a loop, an async function).
  There, `await app.run(...)`.
- `asyncio.gather` raises the first error and lets the other runs go on;
  `return_exceptions=True` returns the errors in place of the results.
- A run of an application that is not started connects to the daemon and
  enters the lifespan on its own: slow for many runs, and each run gets its own
  state.
- The result is validated after the sandbox is deleted: nothing in the sandbox
  is left to inspect when the annotation is wrong (use `keep=True` while
  debugging).
