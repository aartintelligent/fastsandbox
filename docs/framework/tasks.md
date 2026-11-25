# Tasks

A task is a function declared with
[`@app.task`][fastsandbox.FastSandbox.task]: each run creates its sandbox,
runs the function and deletes the sandbox. This page covers the options of a
task, the defaults the application gives them, timeouts, synchronous
functions, and the [`Task`][fastsandbox.Task] object the decorator returns.

## Declaring a task

`@app.task` is used bare, as in [the first application](index.md), or with
options:

```python title="docs_src/tasks/options.py" hl_lines="3 6-14"
--8<-- "docs_src/tasks/options.py"
```

| Option | Default | What it does |
|---|---|---|
| `name` | The name of the function | The name the task is run by. A second task of the same name raises [`TaskError`][fastsandbox.exceptions.TaskError]. |
| `kit` | The kit of the application | The kit of the sandbox: a name such as `"shell"` or `"claude"`, a [`Kit`][fastsandbox.Kit] composed with mixins and kit arguments, or a [`KitPackage`][fastsandbox.KitPackage] already compiled. |
| `network` | No rule | The [network rules](network.md) of the sandbox. |
| `timeout` | None | The deadline of the function (see [Timeouts](#timeouts)). |
| `env` | None | Environment variables of the sandbox. |
| `cpus` | The daemon's | Number of virtual CPUs. |
| `memory` | The daemon's | Memory limit in `sbx` notation, e.g. `"4g"`. |
| `keep` | `False` | Keeps the sandbox after the run, to look into it. |
| `description` | The docstring | The documentation of the task. |
| `max_concurrency` | None | How many runs of this task may run at once. |

The application has two defaults of its own:
[`FastSandbox(kit=...)`][fastsandbox.FastSandbox] is the kit of the tasks that
name none, `"shell"` unless set, and `max_concurrency` bounds how many runs of
any of its tasks hold a sandbox at once. A run waits for a free slot of both
bounds before it creates its sandbox.

The sandbox of a run is named after the application and the task, with a
random suffix: `builds-describe-sandbox-1a2b3c4d`.

!!! tip "Keeping a sandbox"
    With `keep=True`, the sandbox is not deleted after the run: `sbx ls` lists
    it, and the client reaches it by name with `client.sandbox(name)`; the task
    can log its name, `ctx.sandbox.name`. It stops once no session holds it,
    and it is then yours to delete.

## Timeouts

`timeout` is a number of seconds, a `datetime.timedelta`, or a duration in
`ms`, `s`, `m`, `h` and `d`, such as `"90s"`, `"10m"`, `"1h30m"`, `"500ms"` or
`"1d"`; an unreadable duration raises
`ValueError` when the task is declared. It bounds the call of the function: the
creation of the sandbox, its preparation and the dependencies come before the
deadline starts. A run that goes over raises
[`SandboxTimeoutError`][fastsandbox.exceptions.SandboxTimeoutError], whose
`after` attribute is the timeout in seconds, and its sandbox is deleted as on
any other error.

Commands have deadlines of their own: `ctx.sandbox.exec(..., timeout=30)`
bounds one command, and `ctx.agent.prompt(..., timeout="15m")` one agent run.

## Synchronous tasks

A task can be a plain `def`. It then runs in a worker thread, so that it does
not block the event loop, and reaches the sandbox, whose methods are
coroutines, through [`ctx.wait`][fastsandbox.Context.wait], which runs an
awaitable on the event loop of the run and returns its result:

```python title="docs_src/tasks/sync_task.py" hl_lines="7 9"
--8<-- "docs_src/tasks/sync_task.py"
```

!!! warning "Timeouts of synchronous tasks"
    When a synchronous task goes over its timeout, the run raises
    `SandboxTimeoutError` and deletes the sandbox, but a thread cannot be
    interrupted: the function keeps running until it returns, and the calls it
    makes to the deleted sandbox fail.

## Logging and progress

[`ctx.log(message)`][fastsandbox.Context.log] logs through the logger of the
task, `fastsandbox.task.<name>`, with the names of the task and the sandbox;
`ctx.logger` is that logger. [`ctx.report_progress`][fastsandbox.Context.report_progress]
reports the progress of the run to the caller, as
[Running tasks](running.md#progress) shows.

## The `Task` object

The decorator returns a [`Task`][fastsandbox.Task], which keeps the options and
the analysis of the signature. Calling it runs the task through its
application: `await describe()` is `await app.run("describe-sandbox")`. The
tasks of an application are in `app.tasks`, by name, and
[`app.get_task(name)`][fastsandbox.FastSandbox.get_task] returns one, or raises
`TaskError` naming the tasks there are. [`Task.input_schema`][fastsandbox.Task.input_schema]
and [`Task.output_schema`][fastsandbox.Task.output_schema] are the JSON schemas
of its inputs and result, as [Inputs and outputs](inputs-outputs.md) explains.
