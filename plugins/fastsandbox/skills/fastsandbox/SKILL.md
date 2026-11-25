---
name: fastsandbox
description: Start here for anything about fastsandbox, the Python package of Docker Sandboxes (sbx) - what it is, what it needs on the machine, how its parts fit (the client, FastSandbox tasks, agent tasks, the fake daemon for tests), the rules every program follows, and which skill to load next. Load when a project imports fastsandbox or lists it as a dependency, when the user wants to run code, commands or coding agents in Docker Sandboxes from Python, or asks how to install, set up or use fastsandbox.
---

# fastsandbox

fastsandbox is a Python package (3.14 or newer) for
[Docker Sandboxes](https://docs.docker.com/ai/sandboxes/): a typed async
client of the socket of `sandboxd`, the daemon of Docker Sandboxes, and
FastSandbox, a declarative framework for tasks and coding agents that run in
throw-away sandboxes (microVMs).

**It is a client.** It runs nothing by itself: every call goes through the
socket of the daemon. Docker Sandboxes must be installed and its daemon running
for the current user (`sbx version` answers) before any program works; only
tests can do without it, against the fake daemon. When something fails to
connect, run `/fastsandbox:doctor`.

## Which layer to use

| The user wants to | Use | Load the skill |
|---|---|---|
| Put a coding agent (Claude Code, Codex, Copilot, Cursor, Devin, Docker Agent, Droid, Kiro, OpenCode) to work on a repository | `@app.agent(...)` | `agents` |
| Run a job in a throw-away sandbox: tests, a build, a script, with inputs and a validated result | `@app.task(...)` | `tasks` |
| Drive sandboxes directly: create, run commands, move files, network policy, credentials, images, events, SSH, MCP, daemon settings, kits | `fastsandbox.connect()` and its handles | `client` |
| Test any of the above without a daemon | `fastsandbox.testing.FakeDaemon`, `fake_package` | `testing` |
| Understand an error or a misbehavior | | `troubleshooting` |

A task and an agent task are built on the client: `ctx.sandbox` in a task is a
client `Sandbox`, so the `client` skill applies inside tasks too.

## Essentials

- **Install order**: Docker Sandboxes, then `uv add fastsandbox` (Python 3.14;
  `uv python install 3.14` gets it), then `fastsandbox info` to check the
  connection. `fastsandbox kits compile <kit>` compiles a kit ahead of its
  first use, which otherwise takes minutes.
- **A sandbox runs while a session is held.** With the client, work inside
  `async with client.create(...) as sandbox, sandbox.running():`; the outer
  block deletes the sandbox, the inner one keeps it running. A task does both
  for you.
- **Everything is async.** From synchronous code: `fastsandbox.run(main())`,
  `fastsandbox.run(task, **inputs)` or `app.run_sync(...)`.
- **The host stays safe by default only if you choose so.** Prefer
  `WorkspaceDir(clone=True)` or `Uploaded(...)` to a read-write
  `WorkspaceDir()`; give unattended code `Network` rules, since the default
  policy of `sbx` may allow everything; read `client.policy.log()` after a run.
- **Results are checked, not trusted.** Run the project's tests in the sandbox
  after an agent; return a validated model, a patch or a file.
- **Secrets**: agent keys are read from the environment of the caller and
  pushed to one sandbox, where the proxy injects them. Never print, log, write
  or hard-code a secret; examples and tests use dummy values.
- **Errors** are classes of `fastsandbox.exceptions`, all deriving from
  `SandboxError`; catch the specific one (`NotFoundError`,
  `SandboxTimeoutError`, `CommandFailedError`, `DaemonUnavailableError`...).
- **Real sandboxes cost time and resources.** Ask before running code that
  creates them on the user's daemon; run the tests, which use the fake daemon,
  freely.

## Workflows of this plugin

| Command | What it does |
|---|---|
| `/fastsandbox:new-project` | Scaffolds a project: an agent application, a task application or a client tool, with tests that run without a daemon |
| `/fastsandbox:add-task` | Adds a task or an agent task, and its test, to an existing application |
| `/fastsandbox:doctor` | Checks the machine, read-only: Docker Sandboxes, Python, the package, the API version, the kits, the agent keys |

The `fastsandbox:sandbox-reviewer` agent reviews code that uses fastsandbox
for the mistakes that cost safety or correctness; use it after writing or
changing such code, before running it against the real daemon.

## Documentation

- Site: https://aartintelligent.github.io/fastsandbox/
- Quickstart: https://aartintelligent.github.io/fastsandbox/get-started/quickstart/
- Installation: https://aartintelligent.github.io/fastsandbox/get-started/installation/
- API reference: https://aartintelligent.github.io/fastsandbox/reference/

This plugin is released with the package and carries its version: it
describes that release of fastsandbox.
