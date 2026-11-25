# Use cases

A sandbox of Docker Sandboxes is a throw-away machine with its own network
policy and its own credentials. fastsandbox fits wherever a Python program
needs to run code it does not want on the host, or to hand a repository to a
coding agent without handing it the machine.

## Checks in a throw-away machine

A test suite, a build or a linter run on a copy of a repository, in a sandbox
that reaches only the hosts it needs and is deleted afterwards. The task
states its kit, its network rules and its deadline; the report it returns is
validated with Pydantic, and the same task runs from Python or from the
command line.

[:lucide-arrow-right: Tasks](../framework/tasks.md) ·
[Host paths](../framework/host-paths.md) ·
[Network rules](../framework/network.md)

## Coding agents, unattended

An agent works on a repository in its own sandbox: Claude Code, Codex,
Copilot, Cursor, Devin, Docker Agent, Droid, Kiro or OpenCode. Its API key is
pushed to that sandbox only, and the tests run after it decide whether its
work holds.

- **A fix on the workspace.** The repository is mounted as the workspace of
  the agent, which changes it in place.
- **A patch from a private clone.** With `WorkspaceDir(clone=True)`, the agent
  works on a clone that goes with the sandbox; its commits leave as a patch to
  review before anything reaches the host.
- **A review, step by step.** `ctx.agent.stream(...)` yields what the agent
  reports as it goes, for a log, a progress bar or an early stop.
- **Several agents on one issue.** Each in its own sandbox, on its own clone;
  the tests pick the patch that holds.

[:lucide-arrow-right: Give it a repository](../agents/repository.md) ·
[Follow its work](../agents/follow.md) ·
[Run several agents](../agents/several.md)

## Agents with tools

The MCP gateway of a sandbox gives its agent the tools of MCP servers: a local
server loaded into the gateway, a remote one behind a token the gateway
injects, or a set chosen when the sandbox is created.

[:lucide-arrow-right: Give it tools](../agents/tools.md)

## Interactive sessions

A shell, or the agent of a kit, relayed to a terminal with its keys and its
window size: a sandbox to explore by hand, opened from a program.

[:lucide-arrow-right: Interactive sessions](../client/interactive.md)

## Tooling around the daemon

The client reaches every route of the daemon, so the tools around it are
Python programs: a watcher on the event stream, an audit of the network policy
and of what sandboxes reached, a cleanup of old sandboxes and images, a report
on disk usage.

[:lucide-arrow-right: Events and prompts](../client/events.md) ·
[Network and policy](../client/network.md) ·
[The daemon](../client/daemon.md)

## Tests

The code that drives sandboxes is tested against a fake daemon that serves the
socket API in memory: no `sbx`, no image, no microVM, so the tests run in any
CI.

[:lucide-arrow-right: Testing](../guides/testing.md)

[:lucide-arrow-right: The examples](../guides/examples.md){ .md-button }
[:lucide-arrow-right: Quickstart](../get-started/quickstart.md){ .md-button .md-button--primary }
