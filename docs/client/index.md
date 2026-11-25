# The client

The client is a typed async API over the `sandboxd` socket of Docker
Sandboxes, which must be installed and running on the machine (see
[Installation](../get-started/installation.md#install-docker-sandboxes)): every operation of `docker-sandbox`, the Rust library it is built
on, with Pydantic models for the payloads and one exception hierarchy for the
errors. This page covers the connection: where the socket is, the deadlines,
the API version, and the handles a client gives. The pages that follow take
one domain each.

## Connecting

[`connect()`][fastsandbox.connect] reaches the socket of the current user,
asks the daemon for its health and checks its API version. It returns a
[`Client`][fastsandbox.Client], the entry point of every other handle.

```python title="docs_src/client/connect.py" hl_lines="5"
--8<-- "docs_src/client/connect.py"
```

A client holds no connection of its own: one is opened per request, so a
program connects once and passes the client, or the handles it gives, where
they are needed. It can be used as an async context manager, which releases
nothing. [`Client.health`][fastsandbox.Client.health] is the
[`Health`][fastsandbox.models.Health] the daemon reported when the client
connected; [`client.daemon.health()`](daemon.md) asks again.

## Where the socket is

Without a `socket` argument, the socket is the one the `sbx` CLI uses, so that
a program and the CLI always talk to the same daemon:

1. the path in the environment variable `DOCKER_SANDBOXES_API`
   ([`fastsandbox.SOCKET_ENV`][fastsandbox.SOCKET_ENV]);
2. `$XDG_STATE_HOME/sandboxes/sandboxes/sandboxd/sandboxd.sock`;
3. the same path under `$HOME/.local/state`.

[`default_socket_path()`][fastsandbox.default_socket_path] gives that path, or
`None` when none of these variables is set. When the daemon cannot be reached,
`connect()` raises
[`DaemonUnavailableError`][fastsandbox.exceptions.DaemonUnavailableError], a
`ConnectionError`. `fastsandbox info` prints the socket, the version of the
daemon and the API range of the library:

```sh
fastsandbox info
```

## Deadlines

Every request has a deadline; past it, the call raises
[`SandboxTimeoutError`][fastsandbox.exceptions.SandboxTimeoutError], a
`TimeoutError` whose `after` attribute says how long it waited.

| Argument | Default | Applies to |
|---|---|---|
| `timeout` | 30 s | ordinary requests |
| `long_operation_timeout` | 15 min | creations, image pulls, commands without a deadline of their own |

A command can have its own deadline, shorter or longer:
`await sandbox.exec("make test", timeout=600)` (see [Commands](commands.md)).

## The API version

The `sandboxd` API is private and changes with `sbx` releases. Each release of
fastsandbox is checked against a range of API versions,
[`SUPPORTED_API`][fastsandbox.SUPPORTED_API], a `(minimum, maximum)` pair whose
maximum is excluded. `version_policy` says what `connect()` does with a daemon
outside it:

| `version_policy` | Outside the supported range |
|---|---|
| `"strict"` (default) | raises [`UnsupportedVersionError`][fastsandbox.exceptions.UnsupportedVersionError], with `found` and `supported` |
| `"warn"` | logs a warning and connects |
| `"ignore"` | connects |

`fastsandbox info` connects with `"warn"`, so that it reports a daemon the
library does not support instead of failing.

## The handles

A client gives one handle per domain of the daemon. Handles are cheap: each
access builds a new one on the same client, and none checks anything until it
is used.

| Handle | Domain | Page |
|---|---|---|
| `client.create(...)` | a new sandbox | [Sandboxes](sandboxes.md) |
| `client.sandboxes` | list, look up, create from a request | [Sandboxes](sandboxes.md) |
| `client.sandbox(name)` | one sandbox, by name | [Sandboxes](sandboxes.md), [Commands](commands.md), [Files](files.md) |
| `client.policy` | the network policy | [Network and policy](network.md) |
| `client.images` | the images of the daemon | [Images](images.md) |
| `client.events`, `client.prompts` | the event and prompt streams | [Events and prompts](events.md) |
| `client.mcp` | the MCP gateway settings | [MCP gateway](mcp.md) |
| `client.daemon` | health, settings, log levels, disk usage | [The daemon](daemon.md) |
| `client.kits`, `client.package(kit)` | kit packages | [Kits](kits.md) |

## From synchronous code

The client is async. [`fastsandbox.run()`][fastsandbox.run] runs a coroutine
from synchronous code, a script or a notebook cell, as `asyncio.run` does; it
also runs the tasks of a FastSandbox application (see
[Running tasks](../framework/running.md)).

```python
fastsandbox.run(main())
```
