# Dependencies

A task asks for what it needs in its signature: a
parameter annotated with one of the handles of the run receives it, and a
parameter annotated with [`Depends`][fastsandbox.Depends] receives the value of
a function called for the run. This page covers both, generator dependencies
and the cache of a run.

## Injection by annotation

A parameter annotated with one of these types is injected, not an input:

| Annotation | Receives |
|---|---|
| [`Context`][fastsandbox.Context] | The context of the run: `sandbox`, `client`, `task`, `app`, `state`, `run_id`, `logger` |
| [`Sandbox`][fastsandbox.Sandbox] | The sandbox of the run, `ctx.sandbox` |
| [`Client`][fastsandbox.Client] | The client of the daemon, `ctx.client` |
| [`AgentRunner`][fastsandbox.AgentRunner] | The agent of the sandbox, `ctx.agent`, for an [agent task](agents.md) |

The name of the parameter does not matter, its annotation does; subclasses of
these types are injected as well.

## Dependencies

`Annotated[T, Depends(function)]` calls `function` for each run, before the
task, and passes what it returns. The dependency itself asks for what it needs
the same way, here the sandbox:

```python title="docs_src/tasks/dependencies.py" hl_lines="16-18 21-24 30-31"
--8<-- "docs_src/tasks/dependencies.py"
```

A dependency is a function, `def` or `async def`, or a generator, plain or
async:

- A function returns the value.
- A generator yields it, once; the code after `yield` runs when the task has
  ended, before the sandbox is deleted. `scratch_dir` creates a directory and
  removes it that way. When the task raised, the error is raised at the
  `yield`: what must run in every case goes in a `try`/`finally` around it.

Its parameters can only be injected ones: the handles of the table above and
other dependencies. A dependency with a plain parameter makes the run raise
[`TaskError`][fastsandbox.exceptions.TaskError].

Dependencies are resolved in the order of the parameters, after the sandbox is
ready and before the timeout of the task starts. A synchronous dependency runs
on the event loop: keep it short, or make it `async`.

## Dependencies of dependencies

A dependency can depend on another, and the value of a function is computed
once per run: every parameter that depends on the same function receives the
same value.

```python title="docs_src/tasks/nested_dependencies.py" hl_lines="16 25-26"
--8<-- "docs_src/tasks/nested_dependencies.py"
```

`input_file` needs `scratch_dir`, and so does `count_lines`: the run creates one
directory, writes the file into it, gives both the same path, and removes the
directory once the task has ended. `Depends(function, use_cache=False)` calls
the function again for each parameter that asks for it.

The values are not shared between runs: each run has its own sandbox, and its
dependencies are resolved anew. What lives as long as the application belongs
to its [lifespan](lifespan.md).
