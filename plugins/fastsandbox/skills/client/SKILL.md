---
name: client
description: The low-level async client of fastsandbox, the Python client of the Docker Sandboxes (sbx) daemon socket. Load before writing or fixing code that calls `fastsandbox.connect()` or uses `Client`, `Sandbox`, `client.create()`, `sandbox.running()`, `exec()`, `attach()`, file transfers (`write_file`, `upload_dir`, archives), ports (`PortBinding`), the network policy (`client.policy`, `RuleChange`, `allow_hosts`), credentials (`CredentialsUpdate`, `CustomSecret`), images, the event and prompt streams, SSH tunnels, the MCP gateway, daemon settings, kit packages (`Kit`, `KitCache`, `KitForge`, `KitPackage`), mixins written in Python (`Mixin`, `KitDescriptor`, `LifecycleStep`), MCP servers for the agent (`McpServer`, `Mixin.mcp`), or that catches the errors of `fastsandbox.exceptions`. For tasks declared with `FastSandbox`, load the tasks skill; for coding agents, the agents skill.
---

# The fastsandbox client

The client is a typed async API over `sandboxd`, the daemon of Docker Sandboxes,
reached through its Unix socket. Docker Sandboxes must be installed and its
daemon running for the current user (`sbx version` answers); without it,
`connect()` raises `DaemonUnavailableError`. Every payload is a Pydantic model
of `fastsandbox.models`, every error a class of `fastsandbox.exceptions`.
Requires Python 3.12 or newer.

```python
import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()
    async with client.create(kit="shell") as sandbox, sandbox.running():
        output = await sandbox.exec("uname -a", check=True)
        print(output.stdout, end="")


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Essentials

- **A sandbox runs only while a session is held.** The daemon stops it about
  30 seconds after its last session closes, and a command, a file transfer or
  a port publication on a stopped sandbox raises `ConflictError`. Work inside
  `async with sandbox.running():`; outside a block, `ensure_running()` returns
  a `Session` to `release()`.
- **`async with client.create(...) as sandbox:` deletes the sandbox on exit**,
  also on an error or a cancellation. An awaited creation
  (`sandbox = await client.create(...)`) stays until the program deletes it:
  `await sandbox.force_delete()`.
- **Commands:** a string runs with `sh -c`, a list is the argument vector. A
  non-zero exit code is an output, not an error: pass `check=True`, or call
  `output.check()`, to raise `CommandFailedError`. A missing program exits 127.
- **Deadlines:** ordinary requests 30 s, long operations (creation, pulls,
  commands without a `timeout`) 15 min, set by `connect()`; past them,
  `SandboxTimeoutError` with `after`.
- **One connection per request.** A `Client` holds none: connect once, pass the
  client around. Handles (`client.sandbox(name)`, `client.policy`…) are cheap
  and check nothing until used.
- **The first sandbox of a kit forges the kit** without the `sbx` CLI: the
  daemon pulls the image of its base kit once, then it takes seconds, and the
  package is kept in memory. A kit only the CLI resolves (a local kit, a mixin
  given by reference) needs `KitCache(sbx="sbx")`. A mixin written in Python
  (`Mixin`) is checked by the rules of the forge as it is made; `Mixin.mcp()`
  gives Claude Code MCP servers (`McpServer`) without the CLI.
- **Network rules add to the daemon policy**, which may allow everything:
  `sandbox.allow_hosts()` does not block the rest, `deny_hosts()` does block.
  Rules of a sandbox go with it; a global rule (`client.policy.apply_all()`
  without `for_sandbox()`) applies to every sandbox and must be removed by its
  identifier when done.
- **Secrets never enter the sandbox**: pushed credentials are injected by its
  proxy. Never print or log a secret value; use dummy values in tests and
  examples; never read the secrets the user stored with `sbx secret set`.
- **Files:** the target directory must exist (`exec(["mkdir", "-p", dir])`
  first); `upload_dir()` and `download_dir()` copy a directory under its own
  name.
- **Global state is shared** with the `sbx` CLI and every sandbox: a program
  that changes daemon settings, log levels or global rules restores them.
- **Tests:** the fake daemon of the testing module serves the life cycle,
  sessions, `exec()`, files, credentials, ports, network rules and image
  loading. Interactive sessions (`attach()`, `agent_session()`) and SSH tunnels
  answer 501; other routes (events, prompts, the policy log, MCP, settings,
  pulls) answer 404 unless the test adds them with `daemon.route()`. Load the
  testing skill.
- From synchronous code, `fastsandbox.run(main())` runs a coroutine.

## Map

| Need | API | Reference |
|---|---|---|
| Connect, socket, deadlines, API version, handles | `connect()`, `Client`, `SUPPORTED_API` | [connecting](reference/connecting.md) |
| Create, find, start, stop, delete, templates | `client.create()`, `Creation`, `Sandboxes`, `Sandbox` | [sandboxes](reference/sandboxes.md) |
| Keep a sandbox running | `sandbox.running()`, `Session` | [sandboxes](reference/sandboxes.md) |
| Run a command to completion | `sandbox.exec()`, `ExecSpec`, `ExecOutput` | [commands](reference/commands.md) |
| Standard input, streamed output, terminals, the kit agent | `sandbox.attach()`, `Interactive` | [interactive](reference/interactive.md) |
| Read and write files and directories | `write_file()`, `read_text()`, `upload_dir()` | [files](reference/files.md) |
| Network rules, checks, activity log | `allow_hosts()`, `client.policy`, `RuleChange` | [network](reference/network.md) |
| Publish ports | `PortBinding`, `publish()` | [ports](reference/ports.md) |
| Secrets and service credentials | `CredentialsUpdate`, `CustomSecret` | [credentials](reference/credentials.md) |
| Images: list, pull, export, load | `client.images`, `Images` | [images](reference/images.md) |
| Event and prompt streams | `client.events`, `client.prompts`, `Stream` | [events](reference/events.md) |
| SSH into a sandbox | `sandbox.ssh_tunnel()`, `SshTunnel` | [ssh](reference/ssh.md) |
| MCP servers of a sandbox | `client.mcp`, `load_mcp_server()` | [mcp](reference/mcp.md) |
| Daemon health, settings, logs, disk | `client.daemon`, `Daemon` | [daemon](reference/daemon.md) |
| Kits, packages, compositions | `Kit`, `KitCache`, `KitPackage` | [kits](reference/kits.md) |
| Errors and retries | `fastsandbox.exceptions` | [errors](reference/errors.md) |

## References

- [reference/connecting.md](reference/connecting.md): before connecting, choosing a socket, a deadline or a version policy.
- [reference/sandboxes.md](reference/sandboxes.md): before creating, looking up, starting, stopping, deleting or saving a sandbox, or holding a session.
- [reference/commands.md](reference/commands.md): before running a command or reading its exit code.
- [reference/interactive.md](reference/interactive.md): before feeding standard input, streaming output, opening a terminal or starting the agent of a kit.
- [reference/files.md](reference/files.md): before moving files, directories or tar archives.
- [reference/network.md](reference/network.md): before changing, checking or auditing network rules.
- [reference/ports.md](reference/ports.md): before publishing a port or reaching a server in a sandbox.
- [reference/credentials.md](reference/credentials.md): before pushing a secret or a service credential.
- [reference/images.md](reference/images.md): before pulling, exporting, loading or removing images.
- [reference/events.md](reference/events.md): before reading the event stream, the prompts, or any `Stream`.
- [reference/ssh.md](reference/ssh.md): before opening an SSH tunnel or configuring the SSH client.
- [reference/mcp.md](reference/mcp.md): before loading MCP servers into a sandbox or checking a registration.
- [reference/daemon.md](reference/daemon.md): before reading or changing daemon settings, log levels or disk usage.
- [reference/kits.md](reference/kits.md): before forging or compiling kits, composing mixins, writing a mixin in Python, giving the agent MCP servers by a mixin, or adding kits to a running sandbox.
- [reference/errors.md](reference/errors.md): before catching errors or deciding on a retry.

Full documentation: https://aartintelligent.github.io/fastsandbox/client/
