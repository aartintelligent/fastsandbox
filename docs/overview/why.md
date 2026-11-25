# Why

[Docker Sandboxes](https://docs.docker.com/ai/sandboxes/) runs code, and
coding agents, in throw-away microVMs. It is driven by the `sbx` CLI, which
talks to a daemon, `sandboxd`, through a Unix socket. Without a library, a
Python program that wants a sandbox runs the CLI and parses what it prints.

fastsandbox talks to the socket instead, through
[`docker-sandbox`](https://crates.io/crates/docker-sandbox), the Rust client of
that socket, and gives Python two layers on top of it: a typed async client,
and FastSandbox, a framework where the work done in a sandbox is a typed
function under a decorator.

## What that changes for you

- **Typed payloads.** Every request and every answer of the daemon is a
  Pydantic model; an editor completes them and mypy checks them. Fields a newer
  daemon adds are kept, not dropped.
- **Errors you can match on.** A missing sandbox is a `NotFoundError`, a
  deadline a `SandboxTimeoutError`, a failed command a `CommandFailedError`,
  each with typed attributes: a handler never reads a message.
  See [Errors](../client/errors.md).
- **Sandboxes that clean up after themselves.** A sandbox created in an
  `async with` block is deleted when the block ends, on an error or a
  cancellation too; a FastSandbox task deletes its sandbox whatever happened.
- **Work declared, not scripted.** `@app.task` and `@app.agent` state the kit,
  the network rules, the deadline and the credentials of a sandbox next to the
  function that uses it; the signature validates the inputs and the result.
  See [FastSandbox](../framework/index.md).
- **Credentials scoped to one sandbox.** The API key of an agent is pushed to
  the sandbox of the run only, where the proxy injects it; the agent sees a
  placeholder. See [Agents](../framework/agents.md#credentials).
- **Tests without a daemon.** A fake daemon serves the socket API in memory, so
  the code that drives sandboxes is tested in any CI. See
  [Testing](../guides/testing.md).

## What it is not

fastsandbox is not a product of Docker, Inc., and not a replacement for `sbx`:
Docker Sandboxes must be installed on the machine, its daemon running, since
fastsandbox connects to its socket; and the CLI compiles the
[kits](../client/kits.md) on their first use. It is not a sandbox runtime
either: the isolation is that of Docker Sandboxes, and fastsandbox decides
only what crosses it (see [Security](../guides/security.md)). Nor is it a
client of the Docker Engine: containers and images outside Docker Sandboxes
belong to the Docker SDK.

[:lucide-arrow-right: See the features](features.md){ .md-button }
[:lucide-arrow-right: Quickstart](../get-started/quickstart.md){ .md-button .md-button--primary }
