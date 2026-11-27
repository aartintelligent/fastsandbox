# Lifespan and state

Some things live longer than a run: a connection to a service, a cache, a
counter. The lifespan of an application runs around its life, and what it
yields is the state every run reads
as `ctx.state`. This page covers the lifespan, the state, and starting an
application once for several runs with `async with app:`.

## A lifespan

```python title="docs_src/tasks/lifespan.py" hl_lines="9-13 16 25 30"
--8<-- "docs_src/tasks/lifespan.py"
```

[`FastSandbox(lifespan=...)`][fastsandbox.FastSandbox] takes a function that
receives the application and returns an async context manager, here written
with `contextlib.asynccontextmanager`:

- The code before `yield` runs when the application starts, on the host.
- What it yields, a mapping or `None`, becomes the state: `ctx.state` in every
  run, and `app.state` while the application is started. `None` gives an empty
  state.
- The code after `yield` runs when the application stops.

While the application is started, every run gets the same state: `sha256`
appends to the list the lifespan created, and the lifespan reads it at the end.
An application that is not started enters its lifespan for each run, and each
run then has a state of its own (see below).

## Starting the application once

Without `async with app:`, every run starts the application for itself: it
connects to the daemon, enters the lifespan, runs the task and stops again. A
program that runs several tasks starts it once instead:

- `async with app:` connects one client, enters the lifespan once, and every
  run inside the block uses both. `main` above runs three tasks with one
  client, and the lifespan prints its summary once, when the block ends.
- An application cannot be started twice at once: entering `async with app:`
  again inside the block raises [`TaskError`][fastsandbox.exceptions.TaskError].
- Once the block has ended, runs start the application for themselves again.

The [dependencies](dependencies.md) of a task, on the contrary, are resolved
for each run: they hold what belongs to one run and its sandbox, the lifespan
what belongs to the application.

## Choosing the client

The application connects to the daemon of the current user, through the socket
[`connect()`][fastsandbox.connect] finds. Its constructor chooses otherwise:

- `socket="/path/to/sandboxd.sock"` connects to another socket;
- `client=` gives a [`Client`][fastsandbox.Client] already connected, used as it
  is;
- `kits=` gives the [`KitCache`][fastsandbox.KitCache] the kits come from,
  instead of the one of the process: one that keeps them in a directory, or
  one that compiles them with the `sbx` CLI (`KitCache(sbx="sbx")`).

That is also how tests point an application at the fake daemon: see
[Testing](../guides/testing.md).
