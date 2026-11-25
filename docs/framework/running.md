# Running tasks

A task runs when it is asked to, from async code, from synchronous code or from
the command line; each run gets its own sandbox. This page covers the ways to
run a task, the progress a task reports, running several at once, and the
errors a run raises.

## From async code

```python title="docs_src/tasks/running.py" hl_lines="25 26"
--8<-- "docs_src/tasks/running.py"
```

- [`await app.run("sha256", text="hello")`][fastsandbox.FastSandbox.run] runs
  a task by name, or given its [`Task`][fastsandbox.Task]; the keyword
  arguments are its inputs. It returns the validated result.
- `await sha256(text="a")` is the same call: the `Task` the decorator returned
  runs through its application.

## From synchronous code

[`app.run_sync("sha256", text="hello")`][fastsandbox.FastSandbox.run_sync] and
[`fastsandbox.run(sha256, text="hello")`][fastsandbox.run] run a task from a
script, a notebook cell or a test, with an event loop of their own;
`fastsandbox.run(main())` runs any coroutine the same way, as the `__main__`
block above does. Neither can be called from a running event loop: there,
await `app.run`.

From a shell, `fastsandbox run` runs a task of a file or a module; see
[Command line](cli.md).

## Progress

A task reports how far it got with
[`await ctx.report_progress(progress, total, message)`][fastsandbox.Context.report_progress];
the caller receives it through the `on_progress` argument of `app.run`, a
function, plain or async, called with the three values. `sha256` reports two
steps, and `show_progress` prints them. The progress is also logged at the
debug level of the logger of the task.

## Several runs at once

Runs are independent: `asyncio.gather` runs several, each in its own sandbox,
as `main` does for three texts. Two bounds limit how many hold a sandbox at
once, the others waiting for a free slot before they create theirs:

- `FastSandbox(max_concurrency=2)`, for every run of the application;
- `@app.task(max_concurrency=...)`, for the runs of one task.

A program that runs many tasks also starts the application once, with
`async with app:`, so that they share one client and one lifespan (see
[Lifespan and state](lifespan.md)).

## Errors

The sandbox of a run is deleted whatever happens, unless the task keeps it
(`keep=True`). The errors a run raises are:

| Error | When |
|---|---|
| `pydantic.ValidationError` | The inputs do not match the signature, before anything is created; or the result does not match the return annotation, after the sandbox is deleted. |
| [`TaskError`][fastsandbox.exceptions.TaskError] | The application has no such task, or the task is misdeclared: two workspaces, a dependency with a plain parameter, an agent kit that describes no agent. |
| [`SandboxTimeoutError`][fastsandbox.exceptions.SandboxTimeoutError] | The task went over its [timeout](tasks.md#timeouts); `after` is the timeout in seconds. |
| [`CommandFailedError`][fastsandbox.exceptions.CommandFailedError] | A command run with `check=True` exited with a non-zero code; `exit_code`, `stdout` and `stderr` tell how. |
| Another [`SandboxError`][fastsandbox.exceptions.SandboxError] | The daemon refused or failed an operation: see [Errors](../client/errors.md). |
| Any other exception | Raised by the function of the task, passed on as it is. |

```python title="docs_src/tasks/errors.py" hl_lines="17-20 22-27"
--8<-- "docs_src/tasks/errors.py"
```

Every error of fastsandbox derives from `SandboxError`, the framework's
included; `ValidationError` is Pydantic's.
