# fastsandbox

Docker Sandboxes for Python: a typed async client of the `sandboxd` socket of
[Docker Sandboxes](https://docs.docker.com/ai/sandboxes/) (`sbx`), and
**FastSandbox**, a declarative framework for tasks and AI coding agents that
run in throw-away sandboxes.

It is built on [`docker-sandbox`](https://crates.io/crates/docker-sandbox), the
Rust client of the socket, through PyO3: every call of the library, its
streams, sessions and errors, with Pydantic models for every payload.

**Documentation**: <https://aartintelligent.github.io/fastsandbox/>

```python
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel
from fastsandbox import Context, FastSandbox, Network, Uploaded, WorkspaceDir

app = FastSandbox("ci-agents")


class Report(BaseModel):
    passed: bool
    summary: str


@app.task(kit="shell", network=Network.allow("pypi.org"), timeout="10m")
async def run_tests(ctx: Context, repo: Annotated[Path, Uploaded("/work")]) -> Report:
    out = await ctx.sandbox.exec("cd /work && make test")
    return Report(passed=out.ok, summary=out.stdout[-500:])


@app.agent("claude", timeout="20m")
async def fix_bug(ctx: Context, repo: Annotated[Path, WorkspaceDir()], issue: str) -> Report:
    await ctx.agent.prompt(f"Fix this issue: {issue}")
    check = await ctx.sandbox.exec("make test", working_dir=str(repo.resolve()))
    return Report(passed=check.ok, summary=check.stdout[-500:])
```

```sh
fastsandbox run app.py fix_bug --repo . --issue "the parser drops the last line"
```

Each call creates a sandbox from its kit, applies its network rules, pushes the
agent's credentials to that sandbox only, keeps it running while the task runs,
validates the inputs and the result with Pydantic, and deletes it.

> This project is not affiliated with Docker, Inc. The `sandboxd` socket API is
> private and changes with `sbx` releases; `docker-sandbox` keeps a map of it per
> version and checks the API version of the daemon when it connects.

## Requirements

fastsandbox is a client of Docker Sandboxes: it connects to the socket of its
daemon, `sandboxd`, and does nothing without it. Install Docker Sandboxes first.

- Linux or macOS, with [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/)
  installed and its daemon running for the current user (`sbx version`).
- Python 3.14 or newer.
- To build from source: a Rust toolchain (1.88 or newer) and
  [uv](https://docs.astral.sh/uv/).
- The `sbx` CLI on `PATH`, to compile kits on first use (see [Kits](#kits)).

## Installation

Install Docker Sandboxes first (see the requirements above), then:

```sh
uv add fastsandbox      # or: pip install fastsandbox
fastsandbox info        # the daemon, its version, the socket
```

The wheels hold the native extension: nothing is compiled. To work on
fastsandbox itself, from a checkout, `uv sync` builds the extension and
installs the package; see [CONTRIBUTING.md](https://github.com/aartintelligent/fastsandbox/blob/main/CONTRIBUTING.md).

## With Claude Code

The repository is also a Claude Code marketplace: its plugin teaches Claude the
whole library and adds `/fastsandbox:new-project`, `/fastsandbox:add-task`,
`/fastsandbox:doctor` and a reviewer of fastsandbox code.

```text
/plugin install fastsandbox --marketplace aartintelligent/fastsandbox
```

## The client

```python
import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()  # checks health and API version
    async with client.create(kit="shell") as sandbox:  # deleted on exit
        async with sandbox.running():  # a sandbox runs while a session is held
            out = await sandbox.exec("uname -a", timeout=30)
            await sandbox.write_file("/tmp/notes.txt", "hello")
            await sandbox.deny_hosts("example.org")  # scoped to this sandbox

            session = await sandbox.attach(["bash"], tty=True, size=(120, 40))
            await session.write("ls\n")
            async for chunk in session:  # OutputChunk(stream, data)
                ...

    async for event in await client.events.subscribe_live():
        print(event.kind, event.action, event.sandbox_name)


fastsandbox.run(main())
```

Every handle and method of `docker-sandbox` is there:

| Domain | Python |
|---|---|
| Client, socket, API version | `connect()`, `Client.health`, `SUPPORTED_API`, `default_socket_path()` |
| Daemon | `client.daemon`: health, info, settings, log levels, disk usage, diagnostics |
| Sandboxes | `client.sandboxes`: list, get, find, create, `create_stream` (progress) |
| Life cycle | `Sandbox`: inspect, start, stop, delete, save as template, working dir, host paths, VM metrics |
| Sessions | `hold_session()`, `ensure_running()`, `async with sandbox.running()` |
| Commands | `exec` (`ExecOutput`), `exec_inspect`, `attach` and `agent_session` (`Interactive`: stdin, output stream, resize, wait, collect) |
| Files | read, write, archives, `upload_dir`, `download_dir` |
| Ports | ports, publish, unpublish, replace the desired port |
| Network | `client.policy`: rules, apply, check, log, profiles; per sandbox: allow, deny, remove hosts |
| Credentials | `push_credentials` (`CredentialsUpdate`, custom secrets), service secrets |
| Kits | `KitPackage`, `KitAgent`, `KitCompiler`, `KitCache`; in-place install and container swap |
| MCP | gateway mode, registration checks, gateway of a sandbox, load and unload servers |
| Images | list, inspect, pull (with progress), load, export, remove |
| Events, prompts | `client.events`, `client.prompts`: typed async streams |
| SSH | `ssh_tunnel()`, a byte tunnel; `fastsandbox ssh-proxy NAME` as a `ProxyCommand` |

Payloads are Pydantic models in `fastsandbox.models`, in the shape of the
library: unknown fields of a newer daemon are kept. Errors derive from
`fastsandbox.SandboxError`: `NotFoundError` (with `status`, `code`,
`operation`), `ConflictError`, `DaemonUnavailableError`, `SandboxTimeoutError`,
`CommandFailedError`, `UnsupportedVersionError`…

## FastSandbox

- **Tasks.** `@app.task(...)` declares a task: its kit, network rules, timeout
  (`"10m"`), environment, CPUs and memory. Synchronous `def` tasks run in a
  thread and reach the sandbox through `ctx.wait(awaitable)`.
- **Agents.** `@app.agent("claude", ...)` declares a task whose sandbox runs a
  coding agent: `claude`, `codex`, `copilot`, `cursor`, `devin`,
  `docker-agent`, `droid`, `kiro` or `opencode`. Its credentials are read from
  the environment (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`…) and pushed as
  secrets of that sandbox only: the proxy injects them, the sandbox only sees a
  placeholder. `ctx.agent.prompt(...)` runs it unattended,
  `ctx.agent.stream(...)` yields what it reports as it goes,
  `ctx.agent.session()` is interactive.
- **Injection by annotation.** `Context`, `Sandbox`, `Client` and
  `AgentRunner` parameters are injected, and `Annotated[T, Depends(fn)]`
  resolves dependencies, generators included.
- **Host paths.** `Annotated[Path, WorkspaceDir()]` mounts a directory as the
  workspace (`clone=True` for a private Git clone), `Mounted(target, read_only)`
  mounts more, `Uploaded(target)` copies the contents in.
- **Lifespan.** `FastSandbox(lifespan=...)` runs around the application; what it
  yields is `ctx.state`. `async with app:` shares one client and lifespan across
  runs.
- **Running.** `await app.run("task", **inputs)`, `app.run_sync(...)`,
  `fastsandbox.run(task, **inputs)`, or the command line.

## The command line

```sh
fastsandbox tasks app.py                     # tasks and their inputs
fastsandbox run app.py run_tests --repo .    # inputs become options
fastsandbox run app.py:app task --input '{"repo": "."}'
fastsandbox kits compile claude              # compile a kit into the cache
fastsandbox info
fastsandbox ssh-proxy my-sandbox             # for ~/.ssh/config ProxyCommand
```

Without an application argument, `fastsandbox` reads `[tool.fastsandbox] app`
in `pyproject.toml`, then looks for `app.py` and `main.py`.

## Kits

The daemon cannot resolve kit references by itself: a kit package captures what
the `sbx` CLI sends for a kit, once, and every later sandbox of that kit is
created from it through the socket alone. `KitCache` compiles packages on first
use into `~/.cache/fastsandbox/kits` (`FASTSANDBOX_KIT_CACHE` overrides it) and
compiles them again when the daemon runs another `sbx` version. The first
compilation of an agent kit can take a few minutes.

## Testing

`fastsandbox.testing` has a fake daemon on a Unix socket and kit packages that
need no `sbx` CLI, for tests that run anywhere:

```python
from fastsandbox import FastSandbox
from fastsandbox.models import ExecOutput
from fastsandbox.testing import FakeDaemon, fake_package


async def test_run_tests(tmp_path):
    async with FakeDaemon() as daemon:
        daemon.on_exec(lambda sandbox, cmd: ExecOutput(exit_code=0, stdout="ok"))
        app = FastSandbox(socket=str(daemon.socket_path), kit=fake_package(tmp_path / "kit"))
        ...
        assert daemon.sandboxes == {}  # deleted after the run
```

Interactive sessions and SSH tunnels upgrade the connection; the fake daemon
does not, so code that uses them is tested against the real daemon.

## Examples

[`examples/`](https://github.com/aartintelligent/fastsandbox/blob/main/examples/README.md) holds one program per use of the library,
as the examples of `docker-sandbox` do, with the same names: the basics, shell
sandboxes (commands, files, network, policy, ports, secrets, SSH, clone mode,
templates, kits, interactive shells, events), the MCP gateway, and every coding
agent `sbx` knows, interactive, with an MCP server, or unattended on a task.

```sh
just example base
just example shell-exec
just example agent-claude ~/my-project -- "explain this project"
```

They talk to the daemon of the current user, create the sandboxes they need
and delete them when they end, also on an error or Ctrl-C.

## Security

- Whoever can reach the socket controls every sandbox; an SSH tunnel is `root`
  in its sandbox, without credentials. Keep both to trusted code.
- The default network policy of `sbx` may allow everything: give unattended
  agents a `Network` and read `client.policy.log()` afterwards.
- Only push credentials a sandbox needs; they are scoped to it and go with it.

## Development

```sh
just ci          # formatting, clippy, ruff, mypy, tests, coverage, dependencies
just test        # the tests, against the fake daemon
just test-live   # the tests against the real daemon (creates sandboxes)
just example X   # one example of examples/ (creates sandboxes)
just docs        # the documentation site, previewed on http://localhost:8000
```

The package `fastsandbox/` is at the root of the repository (the client one
module per domain of `docker-sandbox`, the framework one module per concept),
`docs/` for the pages of the documentation site and
`docs_src/` for their snippets, each tested, `examples/` for the complete programs, `tests/` one file per
behavior, and `fastsandbox-native/` for the Rust extension. `AGENTS.md` details the
architecture, `CONTRIBUTING.md` how to contribute.

## License

Licensed under either of [Apache License, Version 2.0](https://github.com/aartintelligent/fastsandbox/blob/main/LICENSE-APACHE) or
[MIT license](https://github.com/aartintelligent/fastsandbox/blob/main/LICENSE-MIT) at your option.
