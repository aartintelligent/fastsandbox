# Features

A tour of what fastsandbox provides, in the order you meet it. Each table
links to the pages of the documentation that show it in use.

## Sandboxes

| Capability | Details |
|---|---|
| Connection | `connect()` finds the socket of `sbx`, checks the health of the daemon and its API version; deadlines per request and for long operations. |
| Life cycle | Create from a kit, with progress; look up, inspect, start, stop, delete; `async with` deletes on exit; save as a template. |
| Sessions | A sandbox runs while a session is held: `async with sandbox.running()`. |
| Commands | `exec` to completion with exit code and both outputs, `check`, users, working directory, environment, standard input, deadlines. |
| Files | Single files, whole directories in both directions, tar archives. |
| Interactive sessions | A shell or the agent of the kit, with standard input, an output stream, a terminal and its size. |
| Ports | Publish a port of the sandbox on the host, from the start or on a running sandbox. |

[:lucide-arrow-right: Sandboxes](../client/sandboxes.md) ·
[Commands](../client/commands.md) ·
[Files](../client/files.md) ·
[Interactive sessions](../client/interactive.md) ·
[Ports](../client/ports.md)

## Network and credentials

| Capability | Details |
|---|---|
| Rules of one sandbox | Allow and deny hosts for one sandbox; the rules go with it. Hosts are checked as the `sbx` CLI checks them, before anything is sent. |
| Global policy | Rules, checks of a host against the policy, the activity log, profiles. |
| Secrets | Custom secrets and credentials of services, pushed to one sandbox and injected by its proxy; the credentials the daemon withholds, named at creation and on each push. |

[:lucide-arrow-right: Network and policy](../client/network.md) ·
[Credentials](../client/credentials.md)

## The daemon and its services

| Capability | Details |
|---|---|
| Images | List, inspect, pull with progress, load, export, remove. |
| Events and prompts | The event stream and the approval prompts, as typed async streams. |
| SSH | A byte tunnel to the SSH server of a sandbox, and `fastsandbox ssh-proxy` for the SSH client of the system. |
| MCP gateway | The gateway mode, the gateway of a sandbox, servers loaded and unloaded. |
| Daemon | Health, settings, log levels, disk usage, diagnostics, the resources of a sandbox. |
| Kits | Kit packages forged without the `sbx` CLI and kept in memory, or compiled by it when asked; compositions of a kit and mixins, read from their directories or written in Python, MCP servers for the agent included, their arguments checked; kits added to a running sandbox. |
| Errors | One hierarchy under `SandboxError`, a class per kind of failure, typed attributes. |

[:lucide-arrow-right: Images](../client/images.md) ·
[Events and prompts](../client/events.md) ·
[SSH](../client/ssh.md) ·
[MCP gateway](../client/mcp.md) ·
[The daemon](../client/daemon.md) ·
[Kits](../client/kits.md) ·
[Errors](../client/errors.md)

## Tasks

| Capability | Details |
|---|---|
| Declaration | `@app.task` states the kit, the network rules, the deadline (`"10m"`), the environment, the CPUs and the memory of the sandbox of each run. |
| Validation | The parameters are the inputs, validated before the sandbox is created; the return annotation validates the result. |
| Host paths | A directory of the host as the workspace, a private Git clone of it, more mounts, or a copy of its contents. |
| Injection | `Context`, `Sandbox`, `Client` and `AgentRunner` by annotation; `Depends`, generators included. |
| Lifespan and state | What runs around the application, and the state it shares with its runs. |
| Running | `await app.run(...)`, `app.run_sync(...)`, `fastsandbox.run(...)`, several runs at once, progress. |
| Command line | `fastsandbox tasks` and `fastsandbox run`, the inputs as options; `info`, `kits compile`, `ssh-proxy`. |

[:lucide-arrow-right: Tasks](../framework/tasks.md) ·
[Inputs and outputs](../framework/inputs-outputs.md) ·
[Host paths](../framework/host-paths.md) ·
[Dependencies](../framework/dependencies.md) ·
[Lifespan and state](../framework/lifespan.md) ·
[Running tasks](../framework/running.md) ·
[Command line](../framework/cli.md)

## Agents

| Capability | Details |
|---|---|
| The agents of `sbx` | Claude Code, Codex, Copilot, Cursor, Devin, Docker Agent, Droid, Kiro and OpenCode, by the name of their kit. |
| Credentials | Read from the environment of the host and pushed to the sandbox of the run only. |
| Running modes | Unattended (`ctx.agent.prompt`), streamed step by step (`ctx.agent.stream`), or interactive (`ctx.agent.session`). |
| Network | The hosts the agent needs are allowed ahead of the rules of the task. |
| Tools | MCP servers given to Claude Code by a mixin of its kit, without the `sbx` CLI, or loaded into the MCP gateway of its sandbox. |

[:lucide-arrow-right: Quickstart](../get-started/quickstart.md) ·
[Agents](../framework/agents.md) ·
[Give it a repository](../agents/repository.md) ·
[Control its network](../agents/network.md) ·
[Follow its work](../agents/follow.md) ·
[Give it tools](../agents/tools.md) ·
[Run several agents](../agents/several.md)

## Testing

| Capability | Details |
|---|---|
| Fake daemon | `FakeDaemon` serves the socket API in memory and records what a run did. |
| Fake kits | The published kits `shell` and `claude`, served for the forge; `fake_package()` writes kit packages that need neither the `sbx` CLI nor an image. |

[:lucide-arrow-right: Testing](../guides/testing.md)
